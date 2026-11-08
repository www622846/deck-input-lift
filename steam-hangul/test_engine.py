import unittest
import json
from pathlib import Path
from engine import SteamHangulEngine, BACKSPACE, RETURN, TAB, replacement


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SteamHangulEngine()
        self.addCleanup(self.engine.close)
        self.value = ""

    def key(self, character, modifiers=0):
        code = ord(character) if isinstance(character, str) else character
        result = self.engine.process(code, modifiers)
        if result.get('delete'):
            self.value = self.value[:-result['delete']]
        self.value += result.get('insert', '')
        if result.get('passthrough') == 'Backspace':
            self.value = self.value[:-1]
        return self.value

    def test_reported_word_uses_composed_final(self):
        self.assertEqual([self.key(c) for c in 'ㄱㅓㅈㅣㅅ'], ['ㄱ','거','겆','거지','거짓'])

    def test_requested_words_and_compound_syllables(self):
        cases = json.loads(Path(__file__).with_name('word-cases.json').read_text())
        for case in cases:
            with self.subTest(word=case['word']):
                self.engine.reset()
                self.value = ''
                for character in case['keys']:
                    self.key(character)
                self.assertEqual(self.value, case['word'])
                self.assertEqual(self.key(' '), case['word'] + ' ')

    def test_requested_words_in_one_continuous_phrase(self):
        for character in 'ㄱㅓㅈㅣㅅ ㅇㅡㅣㅅㅜㄹ ㅇㅜㅇㅠㄱㅗㅏㄱ ':
            self.key(character)
        self.assertEqual(self.value, '거짓 의술 우유곽 ')

    def test_ascii_keys_from_the_original_steam_layout(self):
        for c in 'rjwlt': self.key(c)
        self.assertEqual(self.value, '거짓')

    def test_word_boundary_preserves_previous_words(self):
        for c in 'rjwlt rjwlt ': self.key(c)
        self.assertEqual(self.value, '거짓 거짓 ')

    def test_double_final_and_following_vowel(self):
        for c in 'rkqtk': self.key(c)
        self.assertEqual(self.value, '갑사')

    def test_backspace_inside_the_current_syllable(self):
        for c in 'rjwlt': self.key(c)
        self.assertEqual(self.key(BACKSPACE), '거지')
        self.assertEqual(self.key(BACKSPACE), '거ㅈ')
        self.assertEqual(self.key(BACKSPACE), '거')
        self.assertEqual(self.key(BACKSPACE), '')

    def test_switching_fields_never_deletes_other_field_contents(self):
        for c in 'rj': self.key(c)
        self.engine.reset(); self.value = 'existing '
        self.assertEqual(self.key('t'), 'existing ㅅ')

    def test_enter_and_tab_pass_through_after_committing_displayed_text(self):
        self.key('r'); self.key('k')
        self.assertEqual(self.engine.process(RETURN)['passthrough'], 'Enter')
        self.assertEqual(self.value, '가')
        self.assertEqual(self.engine.process(TAB)['passthrough'], 'Tab')

    def test_shortcuts_and_key_releases_are_not_consumed(self):
        self.assertFalse(self.engine.process(ord('v'), 4)['consumed'])
        self.assertFalse(self.engine.process(ord('r'), 1 << 30)['consumed'])

    def test_unsupported_keys_do_not_keep_an_old_preedit(self):
        self.key('r'); self.key('k')
        self.assertFalse(self.engine.process(0xFF51)['consumed'])
        self.assertEqual(self.key('t'), '가ㅅ')

    def test_inserted_ascii_is_not_code(self):
        for c in "' ; ": self.key(c)
        self.assertEqual(self.value, "' ; ")

    def test_replacement_uses_unicode_character_offsets(self):
        self.assertEqual(replacement('짓', '짓 '), {'delete': 0, 'insert': ' '})
        self.assertEqual(replacement('지', '짓'), {'delete': 1, 'insert': '짓'})


if __name__ == '__main__':
    unittest.main()
