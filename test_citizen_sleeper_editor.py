#!/usr/bin/env python3
"""
Tests for citizen_sleeper_editor.

Uses a snapshot of a real save file at /tmp/save_snapshot.dat. Falls back to
copying from the live save dir if the snapshot doesn't exist.
"""
import base64
import os
import shutil
import struct
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import citizen_sleeper_editor as cs


SNAPSHOT = Path("/tmp/save_snapshot.dat")


def ensure_snapshot():
    if SNAPSHOT.exists() and SNAPSHOT.stat().st_size > 1000:
        return
    save_dir = cs.default_save_dir()
    saves = cs.list_save_files(save_dir)
    if not saves:
        raise unittest.SkipTest(f"No save files found in {save_dir}")
    shutil.copy2(saves[0], SNAPSHOT)


class TestCryptoLayer(unittest.TestCase):
    def setUp(self):
        ensure_snapshot()
        self.file_bytes = SNAPSHOT.read_bytes()
        self.bf = cs.decrypt_save(self.file_bytes)

    def test_decrypt_yields_bf_magic(self):
        # .NET BinaryFormatter blob always starts with 00 01 00 00 00 FF FF FF FF
        self.assertEqual(self.bf[:9], b"\x00\x01\x00\x00\x00\xff\xff\xff\xff")

    def test_encrypt_produces_same_size(self):
        re_enc = cs.encrypt_save(self.bf)
        # Same plaintext length should produce same ciphertext length
        # (encrypt uses random salt but doesn't change padding)
        self.assertEqual(len(re_enc), len(self.file_bytes))

    def test_encrypt_decrypt_roundtrip(self):
        re_enc = cs.encrypt_save(self.bf)
        bf2 = cs.decrypt_save(re_enc)
        self.assertEqual(bf2, self.bf)

    def test_two_encrypts_differ_due_to_random_salt(self):
        a = cs.encrypt_save(self.bf)
        b = cs.encrypt_save(self.bf)
        self.assertNotEqual(a, b, "salt should make encrypted bytes differ each time")
        # But decrypt to same plaintext
        self.assertEqual(cs.decrypt_save(a), cs.decrypt_save(b))


class TestPairExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_snapshot()
        cls.bf = cs.decrypt_save(SNAPSHOT.read_bytes())
        cls.pairs = cs.list_all_pairs(cls.bf)
        cls.by_key = {k: v for k, v in cls.pairs}

    def test_finds_many_pairs(self):
        self.assertGreater(len(self.pairs), 100, "should find many numeric variables")

    def test_known_stats_present(self):
        # These keys should always exist after a tutorial run
        for key in ("Player_Bits", "Player_Energy", "Player_Condition", "Cycle"):
            self.assertIn(key, self.by_key, f"{key!r} missing from save")

    def test_known_stats_have_sensible_values(self):
        b = self.by_key["Player_Bits"]
        self.assertGreaterEqual(b, 0)
        self.assertLess(b, 100_000, "bits should be a sane game value")
        cond = self.by_key["Player_Condition"]
        self.assertGreaterEqual(cond, 0)
        self.assertLessEqual(cond, 100)
        cyc = self.by_key["Cycle"]
        self.assertGreaterEqual(cyc, 1)


class TestSetValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_snapshot()
        cls.original_bf = cs.decrypt_save(SNAPSHOT.read_bytes())

    def test_set_existing_key_updates_only_that_key(self):
        before = {k: v for k, v in cs.list_all_pairs(self.original_bf)}
        new_bf, old = cs.set_value(self.original_bf, "Player_Bits", 9999.0)
        self.assertEqual(old, before["Player_Bits"])
        after = {k: v for k, v in cs.list_all_pairs(new_bf)}
        self.assertEqual(after["Player_Bits"], 9999.0)
        # Every OTHER key untouched
        for k in before:
            if k == "Player_Bits": continue
            self.assertEqual(before[k], after[k], f"unrelated key {k!r} changed")

    def test_set_missing_key_returns_none_and_no_change(self):
        new_bf, old = cs.set_value(self.original_bf, "ThisKeyDoesNotExist_XYZ", 42)
        self.assertIsNone(old)
        self.assertEqual(new_bf, self.original_bf, "blob must be unchanged on miss")

    def test_set_preserves_blob_size(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", 1)
        self.assertEqual(len(new_bf), len(self.original_bf))

    def test_set_negative_value(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", -5)
        after = {k: v for k, v in cs.list_all_pairs(new_bf)}
        self.assertEqual(after["Player_Bits"], -5.0)

    def test_set_zero(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", 0)
        after = {k: v for k, v in cs.list_all_pairs(new_bf)}
        self.assertEqual(after["Player_Bits"], 0.0)

    def test_set_large_value(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", 2_147_483_647)
        after = {k: v for k, v in cs.list_all_pairs(new_bf)}
        self.assertEqual(after["Player_Bits"], 2_147_483_647.0)

    def test_set_fractional_value(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", 3.14159)
        after = {k: v for k, v in cs.list_all_pairs(new_bf)}
        self.assertAlmostEqual(after["Player_Bits"], 3.14159)

    def test_set_then_encrypt_then_decrypt_preserves_change(self):
        new_bf, _ = cs.set_value(self.original_bf, "Player_Bits", 12345)
        round_tripped = cs.decrypt_save(cs.encrypt_save(new_bf))
        self.assertEqual(
            dict(cs.list_all_pairs(round_tripped))["Player_Bits"], 12345.0
        )

    def test_multiple_sequential_edits(self):
        bf = self.original_bf
        bf, _ = cs.set_value(bf, "Player_Bits", 100)
        bf, _ = cs.set_value(bf, "Player_Energy", 99)
        bf, _ = cs.set_value(bf, "Player_Condition", 50)
        # round-trip through crypto and verify all changes stuck
        bf = cs.decrypt_save(cs.encrypt_save(bf))
        d = dict(cs.list_all_pairs(bf))
        self.assertEqual(d["Player_Bits"], 100.0)
        self.assertEqual(d["Player_Energy"], 99.0)
        self.assertEqual(d["Player_Condition"], 50.0)


class TestAddValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_snapshot()
        cls.bf = cs.decrypt_save(SNAPSHOT.read_bytes())

    def test_add_positive(self):
        before = dict(cs.list_all_pairs(self.bf))["Player_Bits"]
        new_bf, old, new = cs.add_value(self.bf, "Player_Bits", 100)
        self.assertEqual(old, before)
        self.assertEqual(new, before + 100)
        self.assertEqual(dict(cs.list_all_pairs(new_bf))["Player_Bits"], before + 100)

    def test_add_negative(self):
        before = dict(cs.list_all_pairs(self.bf))["Player_Bits"]
        new_bf, old, new = cs.add_value(self.bf, "Player_Bits", -10)
        self.assertEqual(new, before - 10)

    def test_add_missing_key(self):
        new_bf, old, new = cs.add_value(self.bf, "NoSuchKey_QQQ", 5)
        self.assertIsNone(old); self.assertIsNone(new)
        self.assertEqual(new_bf, self.bf)

    def test_add_zero_is_noop(self):
        new_bf, old, new = cs.add_value(self.bf, "Player_Bits", 0)
        self.assertEqual(old, new)
        # plaintext should be identical
        self.assertEqual(new_bf, self.bf)

    def test_chained_adds(self):
        bf = self.bf
        before = dict(cs.list_all_pairs(bf))["Player_Bits"]
        for d in (10, 20, 30, -5):
            bf, _, _ = cs.add_value(bf, "Player_Bits", d)
        self.assertEqual(dict(cs.list_all_pairs(bf))["Player_Bits"], before + 55)


class TestFileOps(unittest.TestCase):
    def setUp(self):
        ensure_snapshot()
        self.tmp = Path("/tmp/cs_editor_test_save.dat")
        shutil.copy2(SNAPSHOT, self.tmp)

    def tearDown(self):
        # Clean up generated files
        for p in Path("/tmp").glob("cs_editor_test_save.dat*"):
            p.unlink(missing_ok=True)

    def test_write_save_creates_backup(self):
        bf = cs.load_save(self.tmp)
        new_bf, _ = cs.set_value(bf, "Player_Bits", 1234)
        bak = cs.write_save(self.tmp, new_bf)
        self.assertTrue(bak.exists())
        # Backup is the OLD content; loading it gives the OLD value
        old_loaded = cs.load_save(bak)
        old_pairs = dict(cs.list_all_pairs(old_loaded))
        self.assertNotEqual(old_pairs["Player_Bits"], 1234)
        # New file has the new value
        new_loaded = cs.load_save(self.tmp)
        new_pairs = dict(cs.list_all_pairs(new_loaded))
        self.assertEqual(new_pairs["Player_Bits"], 1234)

    def test_write_then_read_idempotent(self):
        bf = cs.load_save(self.tmp)
        cs.write_save(self.tmp, bf)
        # round-trip without any change should give back same plaintext
        self.assertEqual(cs.load_save(self.tmp), bf)

    def test_rapid_writes_keep_distinct_backups(self):
        """Multiple writes within the same second must not lose the original."""
        original_bytes = self.tmp.read_bytes()
        bf = cs.load_save(self.tmp)
        baks = []
        for new_val in (1, 2, 3, 4):
            edited, _ = cs.set_value(bf, "Player_Bits", new_val)
            baks.append(cs.write_save(self.tmp, edited))
            bf = cs.load_save(self.tmp)
        self.assertEqual(len(set(baks)), len(baks),
                         f"backups collided: {baks}")
        for b in baks:
            self.assertTrue(b.exists(), f"missing backup: {b}")
        # First backup must contain the ORIGINAL pre-edit bytes
        self.assertEqual(baks[0].read_bytes(), original_bytes)


class TestKeyFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_snapshot()
        cls.bf = cs.decrypt_save(SNAPSHOT.read_bytes())

    def test_no_spurious_keys_with_punctuation(self):
        for k, _ in cs.list_all_pairs(self.bf):
            for ch in ('"', ':', ',', '[', ']', '{', '}', ' '):
                self.assertNotIn(ch, k, f"spurious key leaked through filter: {k!r}")

    def test_all_displayed_keys_are_identifier_shaped(self):
        import re
        pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")
        for k, _ in cs.list_all_pairs(self.bf):
            self.assertRegex(k, pattern, f"key not identifier-shaped: {k!r}")

    def test_known_stats_still_present_after_filter(self):
        keys = {k for k, _ in cs.list_all_pairs(self.bf)}
        for k in ("Player_Bits", "Player_Energy", "Player_Condition", "Cycle"):
            self.assertIn(k, keys)


class TestFriendlyLabel(unittest.TestCase):
    def test_known_stat_returns_explicit_label(self):
        self.assertEqual(cs.friendly_label("Player_Bits"), "Bits (currency)")
        self.assertEqual(cs.friendly_label("Cycle"), "Cycle (current day)")

    def test_inventory_items_labeled_as_items(self):
        self.assertEqual(cs.friendly_label("INV_GirolleCaps"), "Item: Girolle Caps")
        self.assertEqual(cs.friendly_label("INV_ShipmindFragment"), "Item: Shipmind Fragment")
        # Acronym handling
        self.assertEqual(cs.friendly_label("INV_RipperWorm"), "Item: Ripper Worm")

    def test_completion_flags_labeled_as_quests(self):
        self.assertEqual(cs.friendly_label("AMBERHULLREPAIRS_COMPLETE"), "Quest done: Amberhullrepairs")
        self.assertEqual(cs.friendly_label("C_BACKINBUSINESS_COMPLETE"), "Quest done: C Backinbusiness")

    def test_unknown_key_returns_empty(self):
        self.assertEqual(cs.friendly_label("SomeRandomVar"), "")
        self.assertEqual(cs.friendly_label("DragosR"), "")  # quest-progress vars stay unlabeled

    def test_inv_prefix_alone_not_labeled(self):
        # "INV_" with nothing after should not produce "Item: "
        self.assertEqual(cs.friendly_label("INV_"), "")


class TestLabelsAgainstRealSave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_snapshot()
        cls.bf = cs.decrypt_save(SNAPSHOT.read_bytes())
        cls.keys = [k for k, _ in cs.list_all_pairs(cls.bf)]

    def test_inventory_items_get_labeled(self):
        inv_keys = [k for k in self.keys if k.startswith("INV_")]
        self.assertGreater(len(inv_keys), 0, "save should have inventory items")
        for k in inv_keys:
            if k == "INV_New":
                continue  # explicit entry in KNOWN_STATS
            self.assertTrue(
                cs.friendly_label(k).startswith("Item: "),
                f"INV_ key {k!r} not labeled as Item",
            )

    def test_some_quests_labeled(self):
        complete_keys = [k for k in self.keys if k.endswith("_COMPLETE")]
        self.assertGreater(len(complete_keys), 5, "save should have some _COMPLETE flags")
        for k in complete_keys[:5]:
            self.assertTrue(cs.friendly_label(k).startswith("Quest done: "))


class TestFuzzyScore(unittest.TestCase):
    def test_empty_query_keeps_everything(self):
        self.assertGreater(cs.fuzzy_score("", "AnyKey", "any label"), 0)
        self.assertGreater(cs.fuzzy_score("   ", "AnyKey", ""), 0)

    def test_exact_key_beats_prefix_beats_substring(self):
        exact   = cs.fuzzy_score("Player_Bits", "Player_Bits", "Bits")
        prefix  = cs.fuzzy_score("Player",      "Player_Bits", "Bits")
        substr  = cs.fuzzy_score("Bits",        "Player_Bits", "Bits")
        self.assertGreater(exact, prefix)
        self.assertGreater(prefix, substr)
        self.assertGreater(substr, 0)

    def test_substring_in_key_beats_substring_in_label(self):
        key_hit   = cs.fuzzy_score("girolle", "INV_GirolleCaps", "Item: Girolle Caps")
        label_hit = cs.fuzzy_score("currency", "Player_Bits",    "Bits (currency)")
        self.assertGreater(key_hit, 0)
        self.assertGreater(label_hit, 0)
        self.assertGreater(key_hit, label_hit)

    def test_subsequence_match(self):
        # "shfrg" should subseq-match an "Shipmind Fragment"-style key
        s = cs.fuzzy_score("shfrg", "INV_ShipmindFragment", "Item: Shipmind Fragment")
        self.assertGreater(s, 0)

    def test_no_match_returns_zero(self):
        self.assertEqual(cs.fuzzy_score("xyz", "Player_Bits", "Bits"), 0)
        # missing characters (not just out of order)
        self.assertEqual(cs.fuzzy_score("zzz", "Cycle", "Day"), 0)

    def test_case_insensitive(self):
        self.assertGreater(cs.fuzzy_score("PLAYER_BITS", "player_bits", "bits"), 0)
        self.assertGreater(cs.fuzzy_score("PlayEr_BIts", "Player_Bits", ""), 0)

    def test_typical_searches_rank_expected_keys_first(self):
        """Against the real save: typical user queries should find the obvious target."""
        ensure_snapshot()
        bf = cs.decrypt_save(SNAPSHOT.read_bytes())
        keys = [k for k, _ in cs.list_all_pairs(bf)]

        def top_k(query, n=3):
            return [k for _, k in sorted(
                ((cs.fuzzy_score(query, k, cs.friendly_label(k)), k) for k in keys),
                key=lambda x: -x[0],
            )[:n]]

        # Unambiguous targets must rank #1
        self.assertEqual(top_k("girolle", 1), ["INV_GirolleCaps"])
        self.assertEqual(top_k("bits",    1), ["Player_Bits"])
        self.assertEqual(top_k("cycle",   1), ["Cycle"])
        self.assertEqual(top_k("energy",  1), ["Player_Energy"])

        # "condition" legitimately matches multiple keys — both should be in
        # the top results, ordering between them is fine either way.
        top = top_k("condition", 3)
        self.assertIn("Player_Condition", top)
        self.assertIn("DieCondition",     top)


class TestSavePathDiscovery(unittest.TestCase):
    def test_default_save_dir_is_path(self):
        d = cs.default_save_dir()
        self.assertIsInstance(d, Path)

    def test_list_save_files_returns_dats(self):
        d = cs.default_save_dir()
        if d.exists():
            for s in cs.list_save_files(d):
                self.assertTrue(s.name.startswith("save_") and s.name.endswith(".dat"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
