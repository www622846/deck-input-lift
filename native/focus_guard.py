"""Scroll the focused editable component when KWin makes room for the keyboard.

No text/value/clipboard interfaces, keystroke listeners or network.
Only process ancestry and Flatpak instance identity are read to match app peers.
Communication stays on the user's session and accessibility D-Bus buses.
"""
from collections import deque
import signal

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
from process_group import process_group


class FocusGuard:
    def __init__(self):
        self.pid = None
        self.group = None
        self.focused = {}
        self.pending = None
        self.stats = {"requests": 0, "scrolls": 0, "located": False, "errors": 0}
        self.listener = Atspi.EventListener.new(self.on_focus)
        self.listener.register("object:state-changed:focused")

    @staticmethod
    def editable(element):
        return element.get_state_set().contains(Atspi.StateType.EDITABLE)

    def on_focus(self, event, *unused):
        # This event carries focus state, never the contents of an input field.
        if not event.detail1:
            return
        try:
            element = event.source
            group = process_group(element.get_process_id())
            if not self.editable(element):
                self.focused.pop(group, None)
                return
            self.focused[group] = element
            # Bound stale application references over a long desktop session.
            if len(self.focused) > 32:
                self.focused = {group: element}
            if self.group == group:
                self.schedule()
        except GLib.Error:
            pass

    def cancel(self):
        if self.pending is not None:
            GLib.source_remove(self.pending)
            self.pending = None

    def request(self, value):
        try:
            pid = int(value)
        except (TypeError, ValueError):
            return
        if pid <= 0:
            return
        self.pid = pid
        self.group = process_group(pid)
        self.stats["requests"] += 1
        self.schedule()

    def clear(self):
        self.cancel()
        self.pid = None
        self.group = None

    def schedule(self):
        self.cancel()
        # Wayland configure/commit can finish after KWin's first frame event.
        self.pending = GLib.timeout_add(180, self.scroll)

    def locate(self, group):
        root = Atspi.get_desktop(0)
        for index in range(root.get_child_count()):
            try:
                app = root.get_child_at_index(index)
                matches = app is not None and process_group(app.get_process_id()) == group
            except GLib.Error:
                continue
            if not matches:
                continue
            queue = deque([app])
            visited = 0
            # Only inspect focus/editability states, never accessible names or text.
            while queue and visited < 1500:
                element = queue.popleft()
                visited += 1
                try:
                    states = element.get_state_set()
                    if states.contains(Atspi.StateType.FOCUSED) and self.editable(element):
                        return element
                    budget = max(0, 1500 - visited - len(queue))
                    for child in range(min(element.get_child_count(), budget)):
                        item = element.get_child_at_index(child)
                        if item is not None:
                            queue.append(item)
                except GLib.Error:
                    continue
        return None

    def scroll(self):
        self.pending = None
        if self.pid is None:
            return False
        try:
            element = self.focused.get(self.group)
            if element is None or element.get_state_set().contains(Atspi.StateType.DEFUNCT):
                element = self.locate(self.group)
            if element is not None and self.editable(element):
                self.stats["located"] = True
                self.focused[self.group] = element
                component = element.get_component_iface()
                if component is not None:
                    # The application knows its content viewport, including browser
                    # toolbars and nested scrolling containers. Visible fields stay put.
                    if component.scroll_to(Atspi.ScrollType.ANYWHERE):
                        self.stats["scrolls"] += 1
        except GLib.Error:
            self.stats["errors"] += 1
            self.focused.pop(self.group, None)
        return False


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("org.deckinputlift.FocusGuard", bus=bus, do_not_queue=True)
    guard = FocusGuard()

    class Service(dbus.service.Object):
        @dbus.service.method("org.deckinputlift.FocusGuard", in_signature="s", out_signature="")
        def Request(self, pid):
            guard.request(str(pid))

        @dbus.service.method("org.deckinputlift.FocusGuard", in_signature="", out_signature="")
        def Clear(self):
            guard.clear()

        @dbus.service.method("org.deckinputlift.FocusGuard", in_signature="", out_signature="s")
        def Status(self):
            import json
            return json.dumps({**guard.stats, "targetPid": guard.pid, "targetGroup": guard.group,
                               "cachedGroups": list(guard.focused)})

    service = Service(bus, "/org/deckinputlift/FocusGuard")
    loop = GLib.MainLoop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, lambda: loop.quit() or False)
    print("Deck Input Lift focus guard ready", flush=True)
    loop.run()


if __name__ == "__main__":
    main()
