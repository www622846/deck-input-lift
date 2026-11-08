"""An in-memory two-set Hangul composer backed by the system libhangul.

This module receives only key requests from the Steam keyboard bridge. It does
not read application text, save input, or communicate over a network.
"""
import ctypes
from ctypes.util import find_library
from functools import lru_cache


JAMO_KEYS = dict(zip(
    "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡㅃㅉㄸㄲㅆㅒㅖ",
    "qwertyuiopasdfghjklzxcvbnmQWERTOP",
))


@lru_cache(maxsize=1)
def load_library():
    name = find_library("hangul")
    if not name:
        raise RuntimeError("libhangul is required (already present on the tested Steam Deck)")
    lib = ctypes.CDLL(name)
    context = ctypes.c_void_p
    ucs4 = ctypes.POINTER(ctypes.c_uint32)
    declarations = {
        "hangul_ic_new": ([ctypes.c_char_p], context),
        "hangul_ic_delete": ([context], None),
        "hangul_ic_reset": ([context], None),
        "hangul_ic_process": ([context, ctypes.c_int], ctypes.c_bool),
        "hangul_ic_backspace": ([context], ctypes.c_bool),
        "hangul_ic_get_preedit_string": ([context], ucs4),
        "hangul_ic_get_commit_string": ([context], ucs4),
        "hangul_ic_flush": ([context], ucs4),
    }
    for name, (arguments, result) in declarations.items():
        function = getattr(lib, name)
        function.argtypes = arguments
        function.restype = result
    return lib


def unicode_string(pointer):
    if not pointer:
        return ""
    result = []
    for index in range(128):
        codepoint = pointer[index]
        if not codepoint:
            return "".join(result)
        result.append(chr(codepoint))
    raise RuntimeError("Unexpected libhangul string length")


class Composer:
    def __init__(self):
        self.lib = load_library()
        self.context = self.lib.hangul_ic_new(b"2")
        if not self.context:
            raise RuntimeError("Could not create a two-set Hangul context")
        self.committed = ""

    def close(self):
        if self.context:
            self.lib.hangul_ic_delete(self.context)
            self.context = None

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def _check(self):
        if not self.context:
            raise RuntimeError("Composer is closed")

    @property
    def preedit(self):
        self._check()
        return unicode_string(self.lib.hangul_ic_get_preedit_string(self.context))

    @property
    def text(self):
        return self.committed + self.preedit

    def _apply(self, character, literal):
        if literal:
            self.committed += unicode_string(self.lib.hangul_ic_flush(self.context))
            self.committed += character
            return
        consumed = self.lib.hangul_ic_process(self.context, ord(character))
        self.committed += unicode_string(self.lib.hangul_ic_get_commit_string(self.context))
        if not consumed:
            self.committed += unicode_string(self.lib.hangul_ic_flush(self.context))
            self.committed += character

    def key(self, character):
        """Process one ASCII key or a two-set compatibility jamo from our UI."""
        self._check()
        if not isinstance(character, str) or len(character) != 1:
            raise ValueError("Exactly one key is required")
        character = JAMO_KEYS.get(character, character)
        if ord(character) > 127 or (ord(character) < 32 and character not in "\n\t"):
            raise ValueError("Use an ASCII key, compatibility jamo, or insert_literal")
        self._apply(character, False)
        return self.text

    def keys(self, characters):
        for character in characters:
            self.key(character)
        return self.text

    def insert_literal(self, text):
        self._check()
        for character in text:
            self._apply(character, True)
        return self.text

    def finish_syllable(self):
        self._check()
        self.committed += unicode_string(self.lib.hangul_ic_flush(self.context))
        return self.text

    def backspace(self):
        """Delete a composing jamo, or one already-committed character."""
        self._check()
        if not self.lib.hangul_ic_backspace(self.context):
            self.committed = self.committed[:-1]
        return self.text

    def clear(self):
        self._check()
        self.lib.hangul_ic_reset(self.context)
        self.committed = ""
