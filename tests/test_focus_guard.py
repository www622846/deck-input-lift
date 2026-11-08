"""Exercise scroll lifecycle with no platform dependencies or text interfaces."""
from pathlib import Path
import importlib.util
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch


class PlatformError(Exception):
    pass


class Element:
    def __init__(self, pid=42, focused=True, editable=True, defunct=False, children=()):
        self.pid, self.focused, self.editable, self.defunct = pid, focused, editable, defunct
        self.children = list(children)
        self.scrolls = 0

    def get_process_id(self):
        return self.pid

    def get_state_set(self):
        return SimpleNamespace(contains=lambda state: {
            'editable': self.editable, 'focused': self.focused, 'defunct': self.defunct
        }[state])

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_component_iface(self):
        return self

    def scroll_to(self, kind):
        self.scrolls += 1
        return True

    def get_name(self):
        raise AssertionError('Do not inspect typed text or accessible names')

    def get_text_iface(self):
        raise AssertionError('Do not read the text interface')


class FocusGuardTests(unittest.TestCase):
    def setUp(self):
        self.timers = {}
        self.sequence = 0
        self.desktop = Element(pid=0, focused=False, editable=False)
        glib = SimpleNamespace(Error=PlatformError, timeout_add=self.schedule,
                               source_remove=lambda timer: self.timers.pop(timer, None))
        atspi = SimpleNamespace(StateType=SimpleNamespace(EDITABLE='editable', FOCUSED='focused', DEFUNCT='defunct'),
                                ScrollType=SimpleNamespace(ANYWHERE='anywhere'),
                                EventListener=SimpleNamespace(new=lambda callback: SimpleNamespace(register=lambda event: None)),
                                get_desktop=lambda index: self.desktop)
        dbus = ModuleType('dbus'); dbus.service = ModuleType('dbus.service')
        glib_module = ModuleType('dbus.mainloop.glib'); glib_module.DBusGMainLoop = lambda **kwargs: None
        gi = ModuleType('gi'); gi.require_version = lambda *args: None
        repository = ModuleType('gi.repository'); repository.Atspi, repository.GLib = atspi, glib
        processes = ModuleType('process_group'); processes.process_group = int
        modules = {'dbus': dbus, 'dbus.service': dbus.service, 'dbus.mainloop': ModuleType('dbus.mainloop'),
                   'dbus.mainloop.glib': glib_module, 'gi': gi, 'gi.repository': repository, 'process_group': processes}
        path = Path(__file__).resolve().parents[1] / 'native/focus_guard.py'
        spec = importlib.util.spec_from_file_location('focus_guard_test_subject', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        self.guard = module.FocusGuard()

    def schedule(self, milliseconds, callback):
        self.sequence += 1
        self.timers[self.sequence] = callback
        return self.sequence

    def flush(self):
        for timer in list(self.timers):
            callback = self.timers.pop(timer, None)
            if callback:
                callback()

    def focus(self, element):
        self.guard.on_focus(SimpleNamespace(detail1=1, source=element))

    def test_repeated_focus_notifications_during_composition_do_not_scroll_again(self):
        field = Element()
        self.focus(field)
        self.guard.request('42')
        self.flush()
        self.assertEqual(field.scrolls, 1)
        for _ in range(5):
            self.focus(field)
            self.flush()
        self.assertEqual(field.scrolls, 1)

    def test_switching_fields_in_the_same_app_scrolls_the_new_field(self):
        first, second = Element(), Element()
        self.focus(first); self.guard.request('42'); self.flush()
        self.focus(second); self.flush()
        self.assertEqual(first.scrolls, 1)
        self.assertEqual(second.scrolls, 1)

    def test_closing_keyboard_cancels_pending_scroll(self):
        field = Element()
        self.focus(field); self.guard.request('42'); self.guard.clear(); self.flush()
        self.assertEqual(field.scrolls, 0)

    def test_invalid_process_ids_are_ignored(self):
        for value in ('', 'not-a-pid', '-1', '0'):
            self.guard.request(value)
        self.assertIsNone(self.guard.pid)
        self.assertEqual(self.timers, {})

    def test_stale_app_is_skipped_when_locating_focused_field(self):
        class DeadApp(Element):
            def get_process_id(self):
                raise PlatformError('app exited')
        field = Element()
        self.desktop.children = [DeadApp(), Element(focused=False, editable=False, children=[field])]
        self.guard.request('42'); self.flush()
        self.assertEqual(field.scrolls, 1)

    def test_defunct_cached_field_is_replaced(self):
        stale, field = Element(defunct=True), Element()
        self.guard.focused[42] = stale
        self.desktop.children = [Element(focused=False, editable=False, children=[field])]
        self.guard.request('42'); self.flush()
        self.assertEqual(stale.scrolls, 0)
        self.assertEqual(field.scrolls, 1)


if __name__ == '__main__':
    unittest.main()
