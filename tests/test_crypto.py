"""Tests for :mod:`cs_save_editor.crypto`."""

from __future__ import annotations

from pathlib import Path

import cs_save_editor as cs


def test_decrypt_yields_bf_magic(snapshot_bf: bytes) -> None:
    # .NET BinaryFormatter blobs always start with 00 01 00 00 00 FF FF FF FF.
    assert snapshot_bf[:9] == b"\x00\x01\x00\x00\x00\xff\xff\xff\xff"


def test_encrypt_produces_same_size(snapshot_path: Path, snapshot_bf: bytes) -> None:
    re_enc = cs.encrypt_save(snapshot_bf)
    assert len(re_enc) == len(snapshot_path.read_bytes())


def test_encrypt_decrypt_roundtrip(snapshot_bf: bytes) -> None:
    assert cs.decrypt_save(cs.encrypt_save(snapshot_bf)) == snapshot_bf


def test_two_encrypts_differ_due_to_random_salt(snapshot_bf: bytes) -> None:
    a = cs.encrypt_save(snapshot_bf)
    b = cs.encrypt_save(snapshot_bf)
    assert a != b, "salt should make encrypted bytes differ each time"
    assert cs.decrypt_save(a) == cs.decrypt_save(b)
