"""Inspect composition events only in Deck Input Lift's isolated test page."""
import argparse
import json
import socket

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("init", "read"))
parser.add_argument("--dynamic-title", action="store_true")
parser.add_argument("--summary", action="store_true")
args = parser.parse_args()
sock = socket.create_connection(("127.0.0.1", 2828), timeout=5)
sock.settimeout(10)


def receive():
    prefix = b""
    while True:
        c = sock.recv(1)
        if c == b":":
            break
        if not c:
            raise EOFError()
        prefix += c
    remaining = int(prefix)
    data = b""
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError()
        data += chunk
        remaining -= len(chunk)
    return json.loads(data)


sequence = 0


def command(name, params):
    global sequence
    sequence += 1
    data = json.dumps([0, sequence, name, params]).encode()
    sock.sendall(str(len(data)).encode() + b":" + data)
    reply = receive()
    if reply[2]:
        raise RuntimeError(reply[2])
    return reply[3]


receive()
session = command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"browserName": "firefox"}}})
caps = session.get("capabilities", session.get("value", {}).get("capabilities", {}))
assert caps.get("moz:profile", "").endswith("/deck-input-lift-test"), "Not a test profile"
script = """
if (location.href !== 'file:///home/deck/Downloads/deck-input-lift-test.html')
    throw new Error('Refusing to inspect a non-test page');
const el = document.getElementById('search');
"""
if args.action == "init":
    script += """
el.value = '';
document.title = 'Deck Input Lift test';
window.imeEvents = [];
if (!window.imeListenerInstalled) {
    for (const type of ['compositionstart','compositionupdate','compositionend','beforeinput','input'])
        el.addEventListener(type, e => window.imeEvents.push({type:e.type, data:e.data,
            composing:e.isComposing, value:el.value}));
    window.imeListenerInstalled = true;
}
el.focus();
return {initialized:true};
"""
    if args.dynamic_title:
        script = script.replace("el.focus();", "el.oninput = () => { document.title = 'Deck Input Lift test ' + el.value; }; el.focus();")
else:
    script += ("return {value:el.value, eventCount:(window.imeEvents || []).length};" if args.summary else
               "return {value:el.value, events:window.imeEvents || []};")
try:
    result = command("WebDriver:ExecuteScript", {"script": script, "args": [], "newSandbox": False})
    print(json.dumps(result.get("value", result), ensure_ascii=False, indent=2))
finally:
    command("WebDriver:DeleteSession", {})
    sock.close()
