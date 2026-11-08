"""On-device WebDriver check against the dedicated local Firefox test profile.

Only inspects our own fixture page; never navigates or reads personal tabs.
"""
import json
import socket
import subprocess
import time

sock = socket.create_connection(("127.0.0.1", 2828), timeout=10)
sock.settimeout(15)


def receive():
    length = b""
    while True:
        part = sock.recv(1)
        if not part:
            raise RuntimeError("Marionette disconnected")
        if part == b":":
            break
        length += part
    remaining = int(length)
    data = b""
    while remaining:
        part = sock.recv(remaining)
        if not part:
            raise RuntimeError("Marionette disconnected")
        data += part
        remaining -= len(part)
    return json.loads(data)


sequence = 0


def command(name, parameters=None):
    global sequence
    sequence += 1
    data = json.dumps([0, sequence, name, parameters or {}]).encode()
    sock.sendall(str(len(data)).encode() + b":" + data)
    reply = receive()
    if reply[0] != 1 or reply[1] != sequence or reply[2]:
        raise RuntimeError(str(reply))
    return reply[3]


receive()
command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"browserName": "firefox"}}})
measure = """
if (location.href !== 'file:///home/deck/Downloads/deck-input-lift-test.html')
    throw new Error('Refusing to inspect a non-test page');
const el = document.getElementById('search');
const r = el.getBoundingClientRect();
return {height:innerHeight, width:innerWidth, top:r.top, bottom:r.bottom,
    focused:document.activeElement===el, visible:r.top>=0 && r.bottom<=innerHeight,
    unchanged:el.value==='스팀덱 검색 테스트'};
"""


def state():
    reply = command("WebDriver:ExecuteScript", {"script": measure, "args": [], "newSandbox": True})
    return reply.get("value", reply)


try:
    command("WebDriver:Navigate", {"url": "file:///home/deck/Downloads/deck-input-lift-test.html"})
    time.sleep(1)
    before = state()
    print("BEFORE", json.dumps(before), flush=True)
    subprocess.run(["steam", "-ifrunning", "steam://open/keyboard"], capture_output=True, timeout=8)
    time.sleep(2)
    after = state()
    print("KEYBOARD_OPEN", json.dumps(after), flush=True)
    subprocess.run(["python3", "/home/deck/.local/share/deck-input-lift/kwin-probe.py"], check=True)
    subprocess.run(["python3", "/home/deck/.local/share/deck-input-lift/kwin-probe.py", "--code",
                    "/home/deck/.local/share/deck-input-lift/close-keyboard.js"], check=True)
    time.sleep(1)
    closed = state()
    print("KEYBOARD_CLOSED", json.dumps(closed), flush=True)
    assert after["height"] < before["height"], "Keyboard did not reduce Firefox viewport"
    assert after["visible"], "Focused input is hidden after viewport shrink"
    assert after["unchanged"], "Test text changed"
    assert closed["height"] == before["height"], "Viewport not restored"
    print("PASS: real Firefox input remains visible, text unchanged, viewport restored")
finally:
    command("WebDriver:DeleteSession")
    sock.close()
