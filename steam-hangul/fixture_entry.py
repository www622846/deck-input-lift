"""Isolated GTK entry used for on-device Steam keyboard tests, not user data.

The test value stays in memory. This file is not installed by install.sh.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
name = dbus.service.BusName('org.deckinputlift.HangulTestField', bus=bus, do_not_queue=True)
window = Gtk.Window(title='Steam Hangul Test Field')
window.set_default_size(800, 210)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
box.set_border_width(20)
box.pack_start(Gtk.Label(label='Steam 한글 조합 테스트 전용 입력칸'), False, False, 0)
entry = Gtk.Entry()
entry.set_placeholder_text('테스트 문구만 입력하세요')
box.pack_start(entry, False, False, 0)
window.add(box)


class TestField(dbus.service.Object):
    @dbus.service.method('org.deckinputlift.HangulTestField', in_signature='', out_signature='s')
    def Read(self):
        return entry.get_text()

    @dbus.service.method('org.deckinputlift.HangulTestField', in_signature='', out_signature='')
    def Clear(self):
        entry.set_text('')
        entry.grab_focus()


service = TestField(bus, '/org/deckinputlift/HangulTestField')
window.connect('destroy', Gtk.main_quit)
window.show_all()
entry.grab_focus()
Gtk.main()
