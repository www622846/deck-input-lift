"""Run against the actual system libhangul: python3 -m unittest -v."""
import unittest
from composer import Composer


class ComposerTests(unittest.TestCase):
    def setUp(self):
        self.composer = Composer()
        self.addCleanup(self.composer.close)

    def test_reported_final_consonant_at_each_step(self):
        result = [self.composer.key(key) for key in "ㄱㅓㅈㅣㅅ"]
        self.assertEqual(result, ["ㄱ", "거", "겆", "거지", "거짓"])

    def test_double_final_consonant(self):
        self.assertEqual(self.composer.keys("ㄱㅏㅂㅅ"), "값")

    def test_final_moves_to_the_next_syllable(self):
        self.assertEqual(self.composer.keys("ㄱㅏㄴㅏ"), "가나")

    def test_double_final_splits_when_vowel_follows(self):
        self.assertEqual(self.composer.keys("ㄱㅏㅂㅅㅏ"), "갑사")

    def test_consonant_cluster_before_new_initial(self):
        self.assertEqual(self.composer.keys("ㅇㅣㄹㄱㅇㅓ"), "읽어")

    def test_compound_vowel(self):
        self.assertEqual(self.composer.keys("ㄷㅗㅣㄴㅏ"), "되나")

    def test_shifted_keys(self):
        self.assertEqual(self.composer.keys("ㄲㅏㅁㅉㅏㄱ"), "깜짝")

    def test_common_phrase(self):
        self.assertEqual(self.composer.keys("ㅇㅏㄴㄴㅕㅇㅎㅏㅅㅔㅇㅛ"), "안녕하세요")

    def test_space_and_punctuation(self):
        self.assertEqual(self.composer.keys("ㄱㅓㅈㅣㅅ 123!"), "거짓 123!")

    def test_backspace_respects_composing_and_committed_syllables(self):
        self.composer.keys("ㄱㅓㅈㅣㅅ")
        self.assertEqual([self.composer.backspace() for _ in range(5)], ["거지", "거ㅈ", "거", "", ""])

    def test_backspace_after_double_final(self):
        self.composer.keys("ㄱㅏㅂㅅ")
        self.assertEqual(self.composer.backspace(), "갑")
        self.assertEqual(self.composer.backspace(), "가")

    def test_explicit_literal_is_not_reinterpreted_as_hangul(self):
        self.composer.keys("ㄱㅓㅈㅣㅅ")
        self.composer.insert_literal(" https://example.com")
        self.assertEqual(self.composer.text, "거짓 https://example.com")

    def test_clear_starts_a_new_composition(self):
        self.composer.keys("ㄱㅓㅈㅣㅅ")
        self.composer.clear()
        self.assertEqual(self.composer.text, "")
        self.assertEqual(self.composer.keys("ㄱㅏㄴㅏ"), "가나")

    def test_independent_contexts(self):
        self.composer.key("ㄱ")
        with Composer() as other:
            self.assertEqual(other.keys("ㅇㅏ"), "아")
        self.assertEqual(self.composer.key("ㅓ"), "거")

    def test_closed_context_fails_cleanly(self):
        self.composer.close()
        with self.assertRaises(RuntimeError):
            self.composer.key("r")

    def test_all_11172_modern_hangul_syllables(self):
        initial = ["r", "R", "s", "e", "E", "f", "a", "q", "Q", "t", "T", "d", "w", "W", "c", "z", "x", "v", "g"]
        medial = ["k", "o", "i", "O", "j", "p", "u", "P", "h", "hk", "ho", "hl", "y", "n", "nj", "np", "nl", "b", "m", "ml", "l"]
        final = ["", "r", "R", "rt", "s", "sw", "sg", "e", "f", "fr", "fa", "fq", "ft", "fx", "fv", "fg", "a", "q", "qt", "t", "T", "d", "w", "c", "z", "x", "v", "g"]
        for i, first in enumerate(initial):
            for j, middle in enumerate(medial):
                for k, last in enumerate(final):
                    self.composer.clear()
                    actual = self.composer.keys(first + middle + last)
                    expected = chr(0xAC00 + (i * 21 + j) * 28 + k)
                    self.assertEqual(actual, expected, (first, middle, last))


if __name__ == "__main__":
    unittest.main()
