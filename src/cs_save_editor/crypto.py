"""Citizen Sleeper save file encryption layer.

The save file is base64-encoded. After base64-decoding you get an 8-byte
salt followed by DES-CBC ciphertext with PKCS7 padding. The DES key is
derived from the password ``"WakeUpSleeper"`` (recovered from the
Unity-serialized ``CrossPlatformSavedGameDataStorer`` MonoBehaviour) via
PBKDF2-HMAC-SHA1 with the same salt and 1000 iterations. The IV is the
salt itself.

Decrypting yields a UTF-8 string that is *another* base64 layer; decoding
that gives the .NET BinaryFormatter blob handled by :mod:`.format`.
"""

from __future__ import annotations

import base64
import hashlib
import os

from Crypto.Cipher import DES

PASSWORD: bytes = b"WakeUpSleeper"
"""Hard-coded encryption password used by Citizen Sleeper's save system."""

PBKDF2_ITERATIONS: int = 1000
"""PBKDF2 iteration count used by PixelCrushers' EncryptionUtility."""


def _derive_key(password: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, salt, PBKDF2_ITERATIONS, dklen=8)


def decrypt_save(file_bytes: bytes, password: bytes = PASSWORD) -> bytes:
    """Decrypt raw save-file bytes into the inner BinaryFormatter blob."""
    blob = base64.b64decode(file_bytes.strip())
    salt, ct = blob[:8], blob[8:]
    key = _derive_key(password, salt)
    pt = DES.new(key, DES.MODE_CBC, salt).decrypt(ct)
    pad = pt[-1]
    if 1 <= pad <= 8 and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    return base64.b64decode(pt)


def encrypt_save(bf_blob: bytes, password: bytes = PASSWORD) -> bytes:
    """Encrypt a BinaryFormatter blob into save-file bytes (with a fresh random salt)."""
    inner_b64 = base64.b64encode(bf_blob)
    pad = 8 - (len(inner_b64) % 8)
    padded = inner_b64 + bytes([pad]) * pad
    salt = os.urandom(8)
    key = _derive_key(password, salt)
    ct = DES.new(key, DES.MODE_CBC, salt).encrypt(padded)
    return base64.b64encode(salt + ct)
