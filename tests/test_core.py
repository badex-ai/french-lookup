import csv
import json
import tempfile
import unittest
from pathlib import Path

from french_lookup import claude
from french_lookup.cards import CardStore


class SelectionTest(unittest.TestCase):
    def test_single_word_strips_punctuation(self):
        self.assertEqual(claude.clean_selection("  «mangeons», \n"), "mangeons")

    def test_elision_is_one_word(self):
        self.assertTrue(claude.is_single_word("l'homme"))

    def test_phrase_keeps_punctuation_and_collapses_space(self):
        self.assertEqual(claude.clean_selection("j'ai\n  perdu."), "j'ai perdu.")
        self.assertFalse(claude.is_single_word("j'ai perdu"))

    def test_prompt_depends_on_mode(self):
        cfg = claude.Config()
        word = claude.build_command("claude", cfg, "mangeons")
        phrase = claude.build_command("claude", cfg, "j'ai perdu")
        self.assertIn(claude.WORD_PROMPT, word)
        self.assertIn(claude.PHRASE_PROMPT, phrase)


class ParseOutputTest(unittest.TestCase):
    def test_success_is_sanitized(self):
        out = json.dumps({"is_error": False, "result": "**we eat**\n\n<b>manger</b>\n"})
        self.assertEqual(claude.parse_output(out, ""), "we eat\nbmanger/b")

    def test_usage_limit_message(self):
        out = json.dumps({"is_error": True, "result": "Claude AI usage limit reached|1758800000"})
        with self.assertRaisesRegex(claude.LookupError_, "usage limit"):
            claude.parse_output(out, "")

    def test_non_json_failure(self):
        with self.assertRaisesRegex(claude.LookupError_, "internet"):
            claude.parse_output("", "Error: getaddrinfo ENOTFOUND api.anthropic.com")


class CardStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CardStore(Path(self.tmp.name), batch_size=3)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, path):
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    def summary(self):
        return [(p.name, n) for p, n in self.store.batches()]

    def test_accents_quotes_and_newlines_round_trip(self):
        back = 'I got up early\nse lever, "être" <auxiliary>'
        self.assertTrue(self.store.add("Je me suis levée tôt", back))
        path = self.store.batches()[0][0]
        self.assertEqual(
            self.rows(path),
            [["Je me suis levée tôt", 'I got up early\nse lever, "être" auxiliary']],
        )

    def test_duplicates_skipped_case_and_space_insensitive(self):
        self.assertTrue(self.store.add("J'ai perdu", "a"))
        self.assertFalse(self.store.add("  j'ai   PERDU ", "b"))
        self.assertEqual(self.summary(), [("batch-001.csv", 1)])

    def test_full_batch_rolls_over_to_next_number(self):
        for word in "un deux trois quatre".split():
            self.store.add(word, "x")
        self.assertEqual(self.summary(), [("batch-001.csv", 3), ("batch-002.csv", 1)])

    def test_upload_oldest_and_numbers_never_reused(self):
        for word in "un deux trois quatre".split():
            self.store.add(word, "x")
        moved = self.store.mark_oldest_uploaded()
        self.assertEqual(moved, self.store.uploaded_dir / "batch-001.csv")
        self.assertEqual(self.summary(), [("batch-002.csv", 1)])
        # uploading a partial batch, then saving again, starts batch-003
        self.store.mark_oldest_uploaded()
        self.store.add("cinq", "x")
        self.assertEqual(self.summary(), [("batch-003.csv", 1)])

    def test_dedup_survives_upload(self):
        self.store.add("mangeons", "we eat")
        self.store.mark_oldest_uploaded()
        self.assertFalse(self.store.add("mangeons", "we eat"))

    def test_nothing_to_upload(self):
        self.assertIsNone(self.store.mark_oldest_uploaded())
        self.assertEqual(self.summary(), [])


if __name__ == "__main__":
    unittest.main()
