/* Discover the shared keyboard class without reading input values. */
(function () {
    for (const element of Array.from(document.querySelectorAll('[role="button"],button')).slice(0, 16)) {
        const key = Object.keys(element).find(key => key.startsWith('__reactFiber'));
        let fiber = key ? element[key] : null;
        for (let i = 0; fiber && i < 80; i++, fiber = fiber.return) {
            const instance = fiber.stateNode;
            if (instance && typeof instance.TypeKeyInternal === 'function' && instance.props?.bStandalone === true) {
                // Steam renders the keyboard into another window from this
                // shared realm. Its class survives closing/reopening the UI.
                const owner = instance.TypeKeyInternal.constructor('return globalThis')();
                const api = owner.__deckSteamHangul;
                if (!api) return {ready:false};
                const ready = api.attachPrototype(Object.getPrototypeOf(instance));
                if (ready) api.attach(instance);
                return {ready, status:api.status()};
            }
        }
    }
    return {ready:false};
}());
