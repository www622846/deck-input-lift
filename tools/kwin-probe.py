"""Run a short KWin probe via a temporary session-bus callback, then unload it.

Used only during on-device verification. Reports window geometry, not field text.
Requires distro python-dbus and PyGObject; not needed by the installed plugin.
"""
import argparse
import json
import tempfile
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DEFAULT = r"""
var windows = workspace.stackingOrder;
return {
    active: workspace.activeWindow ? String(workspace.activeWindow.internalId) : null,
    windows: windows.map(function(w) {
        var keyboard = /steam/i.test(String(w.resourceClass)) && /keyboard|키보드/i.test(String(w.caption));
        return {
            id: String(w.internalId), app: String(w.resourceClass), role: String(w.windowRole),
            pid: w.pid,
            resourceName: String(w.resourceName),
            keyboard: keyboard, caption: keyboard ? String(w.caption) : undefined,
            frame: w.frameGeometry, hidden: w.hidden, minimized: w.minimized,
            normal: w.normalWindow, special: w.specialWindow, resizeable: w.resizeable,
            fullScreen: w.fullScreen, maximizeMode: w.maximizeMode,
            maximizeGeometryRestore: w.maximizeGeometryRestore, minSize: w.minSize,
            maximizedHorizontally: w.maximizedHorizontally, maximizedVertically: w.maximizedVertically
        };
    })
};
"""
parser = argparse.ArgumentParser()
parser.add_argument("--code", help="File containing JavaScript function body (must return JSON data)")
args = parser.parse_args()
code = Path(args.code).read_text() if args.code else DEFAULT
DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
loop = GLib.MainLoop()
result = []
name = dbus.service.BusName("org.deckinputlift.Probe", bus=bus)


class Reporter(dbus.service.Object):
    @dbus.service.method("org.deckinputlift.Probe", in_signature="s", out_signature="")
    def Report(self, value):
        result.append(json.loads(str(value)))
        loop.quit()


reporter = Reporter(bus, "/org/deckinputlift/Probe")
scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting"), "org.kde.kwin.Scripting")
with tempfile.TemporaryDirectory(prefix="deck-input-probe-") as folder:
    script = Path(folder) / "probe.js"
    script.write_text("""
var result;
try { result = (function() {\n""" + code + """\n})(); }
catch (e) { result = { error: String(e), stack: e.stack }; }
callDBus('org.deckinputlift.Probe', '/org/deckinputlift/Probe',
    'org.deckinputlift.Probe', 'Report', JSON.stringify(result));
""")
    plugin = Path(folder).name
    # Qt exposes overloaded loadScript methods; dbus-python introspection picks
    # the one-argument overload, so use an explicit signature here.
    script_id = bus.call_blocking("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting",
                                  "loadScript", "ss", (str(script), plugin))
    try:
        instance = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting/Script" + str(script_id)), "org.kde.kwin.Script")
        instance.run()
        GLib.timeout_add_seconds(8, lambda: loop.quit() or False)
        if not result:
            loop.run()
    finally:
        scripting.unloadScript(plugin)
    if not result:
        raise SystemExit("KWin probe timed out")
    print(json.dumps(result[0], ensure_ascii=False, indent=2))
