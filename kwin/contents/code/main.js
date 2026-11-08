/* SPDX-License-Identifier: MIT
 * KWin 5/6 script. No text, clipboard, files or network access.
 */
(function () {
    "use strict";
    var gap = Number(readConfig("Gap", 12));
    if (!isFinite(gap) || gap < 0 || gap > 100) gap = 12;
    var extraCaption = String(readConfig("KeyboardCaption", ""));
    var enabled = true;
    var busy = false;
    var tracked = [];
    var session = null;
    var lastApp = null;

    function connect(signal, fn) {
        if (signal && signal.connect) signal.connect(fn);
    }
    function rect(r) {
        return { x: r.x, y: r.y, width: r.width, height: r.height };
    }
    function equal(a, b) {
        return Math.abs(a.x - b.x) < 2 && Math.abs(a.y - b.y) < 2 &&
            Math.abs(a.width - b.width) < 2 && Math.abs(a.height - b.height) < 2;
    }
    function overlap(a, b) {
        return a.x < b.x + b.width && b.x < a.x + a.width &&
            a.y < b.y + b.height && b.y < a.y + a.height;
    }
    function isKeyboard(w) {
        var caption = String(w.caption || "");
        var steam = /steam/i.test(String(w.resourceClass || "") + " " + String(w.resourceName || ""));
        // Do not match browser page titles containing the word "keyboard".
        return steam && (caption === "Steam Input On-screen Keyboard" ||
            caption === "Steam Input 가상 키보드" || caption === "Steam Keyboard" ||
            (extraCaption && caption === extraCaption));
    }
    function visible(entry) {
        var w = entry.w;
        if (entry.removed || entry.hidden || w.deleted || w.minimized || w.hidden) return false;
        if (w.onCurrentDesktop === false || w.onCurrentActivity === false) return false;
        if (typeof w.desktop === "number" && w.desktop > 0 && w.desktop !== workspace.currentDesktop) return false;
        if (w.desktops && w.desktops.length && w.desktops.indexOf(workspace.currentDesktop) < 0) return false;
        if (w.activities && w.activities.length && w.activities.indexOf(workspace.currentActivity) < 0) return false;
        return w.frameGeometry.width > 0 && w.frameGeometry.height > 0;
    }
    function candidate(w) {
        var e = w ? entryFor(w) : null;
        return w && (!e || visible(e)) && !w.deleted && !isKeyboard(w) && !w.specialWindow &&
            !w.minimized && !w.hidden && (w.normalWindow || w.dialog) &&
            w.resizeable !== false && w.moveable !== false;
    }
    function active() {
        return workspace.activeWindow !== undefined ? workspace.activeWindow : workspace.activeClient;
    }
    function entryFor(w) {
        for (var i = 0; i < tracked.length; i++) if (tracked[i].w === w) return tracked[i];
        return null;
    }
    function area(w) {
        return rect(workspace.clientArea(KWin.MaximizeArea, w));
    }
    function maximum(entry, a) {
        if (typeof entry.w.maximizeMode === "number") {
            return { h: Boolean(entry.w.maximizeMode & 1), v: Boolean(entry.w.maximizeMode & 2) };
        }
        if (entry.max) return entry.max;
        // Older KWin versions do not expose readable maximization properties.
        // Before the first state signal, infer each axis from its work-area fit.
        var g = entry.w.frameGeometry;
        return {
            h: Math.abs(g.x - a.x) < 2 && Math.abs(g.width - a.width) < 2,
            v: Math.abs(g.y - a.y) < 2 && Math.abs(g.height - a.height) < 2
        };
    }
    function restore() {
        if (!session) return;
        var s = session;
        session = null;
        callDBus("org.deckinputlift.FocusGuard", "/org/deckinputlift/FocusGuard",
            "org.deckinputlift.FocusGuard", "Clear");
        if (!s.entry.removed && !s.w.deleted) {
            s.w.fullScreen = false;
            s.w.setMaximize(false, false);
            s.w.frameGeometry = rect(s.normal || s.original);
            s.w.setMaximize(s.max.v, s.max.h);
            if (s.fullScreen) s.w.fullScreen = true;
        }
    }
    function fit(w, keyboards) {
        var a = area(w);
        var original = session && session.w === w ? session.original : rect(w.frameGeometry);
        var top = a.y;
        var bottom = a.y + a.height;
        var collision = false;
        for (var i = 0; i < keyboards.length; i++) {
            var k = keyboards[i].w.frameGeometry;
            if (!overlap(original, k)) continue;
            collision = true;
            // Supports a keyboard moved to the upper half as well as bottom-docked.
            if (k.y + k.height / 2 >= a.y + a.height / 2) bottom = Math.min(bottom, k.y - gap);
            else top = Math.max(top, k.y + k.height + gap);
        }
        if (!collision) return null;
        var height = Math.min(original.height, bottom - top);
        // KWin may impose a greater decorated minimum size; do not force impossible fits.
        var minHeight = Math.max(160, w.minSize ? w.minSize.height : 0);
        if (height < minHeight) return null;
        var width = Math.min(original.width, a.width);
        return {
            x: Math.max(a.x, Math.min(original.x, a.x + a.width - width)),
            y: Math.max(top, Math.min(original.y, bottom - height)),
            width: width,
            height: height
        };
    }
    function update() {
        if (busy) return;
        busy = true;
        try {
            var keyboards = [];
            for (var i = 0; i < tracked.length; i++) {
                if (isKeyboard(tracked[i].w) && visible(tracked[i])) keyboards.push(tracked[i]);
            }
            var w = active();
            if (candidate(w)) lastApp = w;
            w = candidate(w) ? w : lastApp;
            var target = enabled && keyboards.length && candidate(w) ? fit(w, keyboards) : null;
            if (!target) { restore(); return; }
            if (session && session.w !== w) restore();
            if (!session) {
                var e = entryFor(w);
                if (!e) return;
                session = {
                    w: w, entry: e, original: rect(w.frameGeometry),
                    max: maximum(e, area(w)), fullScreen: Boolean(w.fullScreen), normal: null
                };
                w.fullScreen = false;
                w.setMaximize(false, false);
                // On X11 the unmaximize is synchronous. On Wayland this may still
                // be the old frame; exact pre-maximize restore size is not guaranteed.
                session.normal = rect(w.frameGeometry);
            }
            if (!equal(w.frameGeometry, target)) w.frameGeometry = target;
            if (w.pid > 0) {
                callDBus("org.deckinputlift.FocusGuard", "/org/deckinputlift/FocusGuard",
                    "org.deckinputlift.FocusGuard", "Request", String(w.pid));
            }
        } finally {
            busy = false;
        }
    }
    function watch(w) {
        if (entryFor(w)) return;
        var e = { w: w, removed: false, hidden: false, max: null };
        tracked.push(e);
        connect(w.frameGeometryChanged, update);
        connect(w.captionChanged, update);
        connect(w.minimizedChanged, update);
        connect(w.hiddenChanged, update);
        connect(w.desktopsChanged, update);
        connect(w.activitiesChanged, update);
        connect(w.windowShown, function () { e.hidden = false; update(); });
        connect(w.windowHidden, function () { e.hidden = true; update(); });
        connect(w.maximizedAboutToChange, function (mode) {
            if (!busy) e.max = { h: Boolean(mode & 1), v: Boolean(mode & 2) };
        });
        connect(w.clientMaximizedStateChanged, function (client, horizontal, vertical) {
            if (!busy) e.max = { h: horizontal, v: vertical };
        });
        update();
    }
    function removed(w) {
        var e = entryFor(w);
        if (e) { e.removed = true; tracked.splice(tracked.indexOf(e), 1); }
        if (lastApp === w) lastApp = null;
        if (session && session.w === w) session = null;
        update();
    }
    connect(workspace.windowAdded || workspace.clientAdded, watch);
    connect(workspace.windowRemoved || workspace.clientRemoved, removed);
    connect(workspace.windowActivated || workspace.clientActivated, update);
    connect(workspace.currentDesktopChanged, update);
    connect(workspace.currentActivityChanged, update);
    // Restore before a monitor layout change; old monitor coordinates may be invalid.
    connect(workspace.screensChanged, function () {
        busy = true;
        try { restore(); } finally { busy = false; }
    });
    connect(workspace.clientMaximizeSet, function (w, horizontal, vertical) {
        var e = entryFor(w);
        if (e && !busy) e.max = { h: horizontal, v: vertical };
    });
    registerShortcut("DeckInputLiftToggle", "Deck Input Lift: toggle and restore", "Meta+Ctrl+K", function () {
        enabled = !enabled;
        update();
    });
    var windows = workspace.stackingOrder || (workspace.clientList ? workspace.clientList() : []);
    // Watch the active app first: Steam's keyboard can take activation while opening.
    if (active()) { watch(active()); if (candidate(active())) lastApp = active(); }
    for (var j = 0; j < windows.length; j++) watch(windows[j]);
    update();
}());
