#!/usr/bin/env python3
"""Opt-in local bridge between Steam's Korean keyboard and libhangul.

Only Steam keyboard key requests and self-generated edits are processed. There
are no application text reads, clipboard reads, disk input logs or remote hosts.
"""
import json
import signal
from pathlib import Path
from urllib.request import urlopen

import gi
gi.require_version("Soup", "3.0")
gi.require_version("Atspi", "2.0")
from gi.repository import Soup, GLib, Atspi

from engine import SteamHangulEngine


class Bridge:
    def __init__(self):
        self.engine = SteamHangulEngine()
        self.session = Soup.Session()
        self.socket = None
        self.connecting = False
        self.sequence = 0
        self.stopping = False
        self.focus = None
        self.prototype_ready = False
        self.discovering = False
        self.discovery_socket = None
        self.patch = (Path(__file__).with_name("patch.js")).read_text()
        self.discovery = (Path(__file__).with_name("discover.js")).read_text()
        self.listener = Atspi.EventListener.new(self.focus_changed)
        self.listener.register("object:state-changed:focused")
        self.loop = GLib.MainLoop()
        self.scan_timer = GLib.timeout_add(1000, self.tick)
        self.tick()

    def evaluate(self, expression):
        return self.command("Runtime.evaluate", {"expression": expression, "returnByValue": True})

    def command(self, method, parameters):
        if self.socket is None:
            return None
        self.sequence += 1
        self.socket.send_text(json.dumps({"id": self.sequence, "method": method, "params": parameters}))
        return self.sequence

    def tick(self):
        if self.stopping:
            return False
        if self.socket is not None:
            self.evaluate("window.__deckSteamHangul?.heartbeat()")
            if not self.prototype_ready and not self.discovering:
                self.discover_keyboard()
            return True
        if self.connecting:
            return True
        for port in (8081, 8080):
            try:
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=.4) as response:
                    pages = json.load(response)
                candidates = [page for page in pages if page.get("title") == "SharedJSContext"]
                if not candidates:
                    continue
                address = candidates[0].get("webSocketDebuggerUrl", "")
                # The helper never follows a debugger address to a remote host.
                from urllib.parse import urlsplit
                parsed = urlsplit(address)
                if parsed.scheme != "ws" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.port != port:
                    continue
                self.connecting = True
                message = Soup.Message.new("GET", address)
                self.session.websocket_connect_async(message, None, None, GLib.PRIORITY_DEFAULT,
                                                     None, self.connected, None)
                break
            except Exception:
                continue
        return True

    def connected(self, session, result, unused):
        self.connecting = False
        try:
            socket = session.websocket_connect_finish(result)
        except GLib.Error:
            return
        if self.stopping:
            socket.close(1000, "stopping")
            return
        self.socket = socket
        self.prototype_ready = False
        self.engine.reset()
        socket.connect("message", self.message)
        socket.connect("closed", self.closed)
        self.command("Runtime.enable", {})
        self.command("Runtime.addBinding", {"name": "__deckHangulNative"})
        self.evaluate(self.patch)
        print("Steam Hangul bridge connected", flush=True)

    def closed(self, socket):
        if self.socket is socket:
            self.socket = None
            self.prototype_ready = False
            self.engine.reset()

    def discover_keyboard(self):
        for port in (8081, 8080):
            try:
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=.4) as response:
                    pages = json.load(response)
                page = next((page for page in pages if page.get('title') in
                            ('Steam Input 가상 키보드', 'Steam Input On-screen Keyboard', 'Steam Keyboard')), None)
                if not page:
                    continue
                from urllib.parse import urlsplit
                address = page.get('webSocketDebuggerUrl','')
                parsed = urlsplit(address)
                if parsed.scheme != 'ws' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.port != port:
                    continue
                self.discovering = True
                self.session.websocket_connect_async(Soup.Message.new('GET',address), None,None,
                    GLib.PRIORITY_DEFAULT,None,self.discovery_connected,None)
                break
            except Exception:
                continue

    def discovery_connected(self, session, result, unused):
        try:
            socket = session.websocket_connect_finish(result)
        except GLib.Error:
            self.discovering = False
            return
        self.discovery_socket = socket
        socket.connect('message',self.discovery_message)
        socket.connect('closed',lambda *_: setattr(self,'discovering',False))
        socket.send_text(json.dumps({'id':1,'method':'Runtime.evaluate','params':{
            'expression':self.discovery,'returnByValue':True}}))

    def discovery_message(self, socket, kind, data):
        if kind != Soup.WebsocketDataType.TEXT:
            return
        try:
            message=json.loads(bytes(data.get_data()).decode('utf-8'))
        except (ValueError,TypeError):
            return
        if message.get('id') != 1:
            return
        try:
            result=message.get('result',{}).get('result',{}).get('value',{})
            self.prototype_ready=bool(result.get('ready'))
        except (ValueError,TypeError,KeyError):
            pass
        finally:
            if self.discovery_socket is socket:
                self.discovery_socket=None
            self.discovering=False
            socket.close(1000,'discovery complete')

    def message(self, socket, kind, data):
        if kind != Soup.WebsocketDataType.TEXT:
            return
        try:
            message = json.loads(bytes(data.get_data()).decode("utf-8"))
            if message.get("method") != "Runtime.bindingCalled":
                return
            parameters = message.get("params", {})
            if parameters.get("name") != "__deckHangulNative":
                return
            request = json.loads(parameters.get("payload", ""))
            identifier = request.get("id")
            if type(identifier) is not int or identifier < 1:
                return
            operation = request.get("op")
            if operation == "reset":
                self.engine.reset()
                result = {"consumed": True}
            elif operation == "key":
                keyval, modifiers = request.get("keyval"), request.get("modifiers", 0)
                if type(keyval) is not int or type(modifiers) is not int or not (0 <= keyval <= 0x10FFFF):
                    raise ValueError("Invalid keyboard request")
                result = self.engine.process(keyval, modifiers)
            else:
                raise ValueError("Unknown keyboard request")
            reply = {"id": identifier, "result": result}
            # JSON encoding treats user-entered quotes as data, never JS source.
            self.evaluate("window.__deckSteamHangul?.receive(" + json.dumps(reply, ensure_ascii=True) + ")")
        except (ValueError, TypeError, KeyError, GLib.Error):
            # Do not log request payloads or composed text. The JS watchdog restores
            # the stock keyboard if a request cannot be completed.
            return

    def focus_changed(self, event, *unused):
        if not event.detail1:
            return
        try:
            element = event.source
            states = element.get_state_set()
            if not states.contains(Atspi.StateType.EDITABLE) and element.get_role() != Atspi.Role.TERMINAL:
                return
            if self.focus == element:
                return
            previous = self.focus
            self.focus = element
            if previous is not None:
                self.engine.reset()
                self.evaluate("window.__deckSteamHangul?.boundary().catch(()=>{})")
        except GLib.Error:
            return

    def stop(self, *unused):
        if self.stopping:
            return False
        self.stopping = True
        if self.socket:
            self.evaluate("window.__deckSteamHangul?.uninstall()")
        GLib.timeout_add(150, lambda: self.loop.quit() or False)
        return False

    def run(self):
        try:
            self.loop.run()
        finally:
            if self.socket:
                self.socket.close(1000, "stopped")
            self.engine.close()


if __name__ == "__main__":
    bridge = Bridge()
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, bridge.stop)
    bridge.run()
