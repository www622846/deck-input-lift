"""Translate only Steam's Korean keyboard keys to ordered Hangul edits.

The buffer is the composition this engine itself produced. No target application
text, clipboard, surrounding text, or physical keyboard events are read.
"""
from composer import Composer, JAMO_KEYS

BACKSPACE = 0xFF08
RETURN = 0xFF0D
TAB = 0xFF09


def replacement(old, new):
    common = 0
    while common < min(len(old), len(new)) and old[common] == new[common]:
        common += 1
    return {"delete": len(old)-common, "insert": new[common:]}


class SteamHangulEngine:
    def __init__(self):
        self.composer = Composer()
        self.rendered = ""

    def close(self):
        self.composer.close()

    def reset(self):
        # Already displayed characters remain in the target app; a new context
        # must never erase a previous context's character.
        self.composer.clear()
        self.rendered = ""

    def process(self, keyval, modifiers=0):
        if not isinstance(keyval, int) or not isinstance(modifiers, int):
            raise ValueError("Integer key and modifier values are required")
        # Shift/Lock are handled by Steam's existing layout. Modifier shortcuts
        # and releases keep using the original implementation.
        if modifiers & ~3:
            self.reset()
            return {"consumed": False}
        if keyval in (RETURN, TAB):
            self.reset()
            return {"consumed": True, "passthrough": "Enter" if keyval == RETURN else "Tab"}
        if keyval == BACKSPACE:
            if not self.composer.preedit:
                self.reset()
                return {"consumed": True, "passthrough": "Backspace"}
            self.composer.backspace()
        else:
            try:
                character = chr(keyval)
            except ValueError:
                return {"consumed": False}
            if character not in JAMO_KEYS and not (32 <= keyval <= 126):
                self.reset()
                return {"consumed": False}
            self.composer.key(character)
        text = self.composer.committed + self.composer.preedit
        edit = replacement(self.rendered, text)
        self.rendered = self.composer.preedit
        self.composer.committed = ""
        return {"consumed": True, **edit}
