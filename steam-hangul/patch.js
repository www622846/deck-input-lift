/* Experimental opt-in bridge for Steam's existing Korean keyboard.
 * The native UI, touch handling, controller handling and layout stay in Steam.
 */
(function () {
    'use strict';
    if (window.__deckSteamHangul) return window.__deckSteamHangul.status();
    const pending = new Map();
    let nextId = 0, tail = Promise.resolve(), patched = null;
    let enabled = true, lastHeartbeat = Date.now();
    let prototypeHook = null;
    const counters = {keys: 0, edits: 0, fallbacks: 0};

    function korean(instance) {
        return instance?.props?.bStandalone === true && instance?.state?.standardLayout?.name === 'korean';
    }
    function request(op, args = {}) {
        return new Promise((resolve, reject) => {
            const id = ++nextId;
            const timer = setTimeout(() => {
                pending.delete(id);
                reject(new Error('Hangul bridge timeout'));
            }, 800);
            pending.set(id, {resolve, reject, timer});
            try { window.__deckHangulNative(JSON.stringify({id, op, ...args})); }
            catch (error) { clearTimeout(timer); pending.delete(id); reject(error); }
        });
    }
    function enqueue(callback) {
        const result = tail.then(callback);
        tail = result.catch(() => {});
        return result;
    }
    function restoreProperty(object, name, descriptor) {
        if (descriptor) Object.defineProperty(object, name, descriptor);
        else delete object[name];
    }
    function detach() {
        if (!patched) return;
        const p = patched;
        patched = null;
        restoreProperty(p.context, 'process_key_event', p.processDescriptor);
        restoreProperty(p.context, 'reset', p.resetDescriptor);
        restoreProperty(p.manager, 'HandleVirtualKeyDown', p.managerDescriptor);
    }
    function install(instance) {
        if (instance?.props?.bStandalone !== true) return false;
        const context = instance.context, manager = instance.props.VirtualKeyboardManager;
        if (!context || !manager || typeof context.process_key_event !== 'function' ||
            typeof manager.HandleVirtualKeyDown !== 'function') return false;
        const p = {
            instance, context, manager, layout: instance.state?.standardLayout?.name,
            process: context.process_key_event, reset: context.reset,
            handle: manager.HandleVirtualKeyDown,
            processDescriptor: Object.getOwnPropertyDescriptor(context, 'process_key_event'),
            resetDescriptor: Object.getOwnPropertyDescriptor(context, 'reset'),
            managerDescriptor: Object.getOwnPropertyDescriptor(manager, 'HandleVirtualKeyDown')
        };
        function originalHandle(key, shift = false) { return p.handle.call(manager, key, shift); }
        try {
            Object.defineProperty(context, 'process_key_event', {configurable: true, writable: true,
                value: function (keyval, keycode, modifiers) {
                    const args = [keyval, keycode, modifiers];
                    if (!enabled || !korean(instance)) {
                        return p.process.apply(context, args);
                    }
                    return enqueue(async () => {
                        if (!enabled) return p.process.apply(context, args);
                        try {
                            const edit = await request('key', {keyval, modifiers});
                            counters.keys++;
                            if (!edit.consumed) return p.process.apply(context, args);
                            if (edit.passthrough) originalHandle(edit.passthrough);
                            else {
                                for (let i = 0; i < edit.delete; i++) originalHandle('Backspace');
                                if (edit.insert) originalHandle(edit.insert);
                                counters.edits++;
                            }
                            return true;
                        } catch (_) {
                            counters.fallbacks++;
                            api.uninstall();
                            return p.process.apply(context, args);
                        }
                    });
                }});
            Object.defineProperty(context, 'reset', {configurable: true, writable: true,
                value: function (...args) {
                    // Steam's IBus resets no longer own Korean composition.
                    // Real field changes are signalled by the native focus watcher.
                    if (enabled && korean(instance)) return Promise.resolve();
                    return enqueue(async () => {
                        try { if (enabled) await request('reset'); } catch (_) { api.uninstall(); }
                        return p.reset.apply(context, args);
                    });
                }});
            Object.defineProperty(manager, 'HandleVirtualKeyDown', {configurable: true, writable: true,
                value: function (...args) {
                    if (!enabled || !korean(instance)) return p.handle.apply(manager, args);
                    // Literal keys, arrows, paste and close must follow earlier
                    // composing keys rather than interleave with their replies.
                    return enqueue(async () => {
                        try { if (enabled) await request('reset'); } catch (_) { api.uninstall(); }
                        return p.handle.apply(manager, args);
                    });
                }});
        } catch (_) {
            patched = p;
            detach();
            return false;
        }
        patched = p;
        return true;
    }
    function attach(instance) {
        if (instance?.props?.bStandalone !== true) return false;
        if (patched?.instance === instance && patched.context === instance.context) {
            const layout = instance.state?.standardLayout?.name;
            if (patched.layout !== layout) {
                patched.layout = layout;
                enqueue(() => request('reset')).catch(() => api.uninstall());
            }
            return true;
        }
        const replacing = Boolean(patched);
        detach();
        const installed = install(instance);
        if (installed && replacing) enqueue(() => request('reset')).catch(() => api.uninstall());
        return installed;
    }
    function find() {
        if (!enabled || prototypeHook) return;
        const elements = document.querySelectorAll('[role="button"],button');
        for (const element of Array.from(elements).slice(0, 16)) {
            const key = Object.keys(element).find(key => key.startsWith('__reactFiber'));
            let fiber = key ? element[key] : null;
            for (let i = 0; fiber && i < 80; i++, fiber = fiber.return) {
                const instance = fiber.stateNode;
                if (instance && typeof instance.TypeKeyInternal === 'function') {
                    if (patched?.instance === instance && patched.context === instance.context) {
                        const layout = instance.state?.standardLayout?.name;
                        if (patched.layout !== layout) {
                            patched.layout = layout;
                            api.boundary().catch(() => api.uninstall());
                        }
                        return;
                    }
                    attach(instance);
                    return;
                }
            }
        }
    }
    const api = {
        heartbeat() { lastHeartbeat = Date.now(); },
        attach,
        attachPrototype(prototype) {
            if (!prototype || typeof prototype.TypeKeyInternal !== 'function') return false;
            if (prototypeHook?.prototype === prototype) return true;
            if (prototypeHook) return false;
            const descriptor = Object.getOwnPropertyDescriptor(prototype, 'TypeKeyInternal');
            const original = prototype.TypeKeyInternal;
            const wrapper = function (...args) {
                if (enabled && this.props?.bStandalone === true) attach(this);
                else if (patched?.context === this.context) {
                    // Inline/Gaming Mode keyboards can share an IBus context.
                    // They must retain their original input path.
                    detach();
                    enqueue(() => request('reset')).catch(() => api.uninstall());
                }
                return original.apply(this, args);
            };
            Object.defineProperty(prototype, 'TypeKeyInternal', {configurable:true,writable:true,value:wrapper});
            prototypeHook = {prototype, descriptor, wrapper};
            return true;
        },
        receive(reply) {
            const waiter = pending.get(reply.id);
            if (!waiter) return;
            pending.delete(reply.id);
            clearTimeout(waiter.timer);
            if (reply.error) waiter.reject(new Error('Hangul engine error'));
            else waiter.resolve(reply.result);
        },
        boundary() { return enqueue(() => enabled ? request('reset') : undefined); },
        status() { return {enabled, prototypeReady:Boolean(prototypeHook), attached: Boolean(patched), korean: Boolean(patched && korean(patched.instance)), ...counters}; },
        uninstall() {
            enabled = false;
            clearInterval(timer);
            detach();
            if (prototypeHook && prototypeHook.prototype.TypeKeyInternal === prototypeHook.wrapper) {
                restoreProperty(prototypeHook.prototype, 'TypeKeyInternal', prototypeHook.descriptor);
            }
            prototypeHook = null;
            for (const waiter of pending.values()) {
                clearTimeout(waiter.timer);
                waiter.reject(new Error('Hangul bridge stopped'));
            }
            pending.clear();
            delete window.__deckSteamHangul;
        }
    };
    const timer = setInterval(() => {
        if (Date.now() - lastHeartbeat > 3500) api.uninstall();
        else find();
    }, 250);
    window.__deckSteamHangul = api;
    find();
    return api.status();
}());
