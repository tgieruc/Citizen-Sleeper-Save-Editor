"""BinaryFormatter + PixelCrushers Lua tag-stream parsing.

After :func:`.crypto.decrypt_save` we have a .NET BinaryFormatter blob that
wraps a ``PixelCrushers.SavedGameData`` object. One of its ``SaveRecord``
entries (key ``"CS Dialogue Manager"``) holds another base64-encoded
BinaryFormatter blob, which itself contains a ``byte[]`` of PixelCrushers'
custom Lua serialisation. Inside that byte array, key/value pairs appear
as length-prefixed tags::

    S<1-byte len><utf8>     string
    N<8-byte little-endian double>   number
    B<1-byte 0/1>           boolean
    T<8-byte header>        table marker

We never need to *understand* the table structure — we just need to find
every ``S<key>`` immediately preceding an ``N<value>`` pair and patch the
8-byte double when asked. Doubles are always 8 bytes wide, so we don't
disturb any surrounding offsets or length prefixes.
"""

from __future__ import annotations

import base64
import re
import struct

_VALID_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")
"""Identifiers we expose to the editor.

The save's Ink scripting state embeds inline JSON strings (e.g. the
``outputStream`` field of a story state). A naive walker treats bytes
inside those strings as fresh ``S`` tags, producing fake keys with
punctuation. Filtering by identifier shape drops those.
"""

_INNER_BF_MARKER = b"AAEAAAD/////AQAAAAAAAAAMAg"
"""Base64 prefix of every .NET BinaryFormatter blob.

We use this to locate the ``CS Dialogue Manager`` SaveRecord's ``value``
string inside the outer BinaryFormatter blob without parsing the BF format
ourselves.
"""

_B64_ALPHABET = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


def find_inner_base64(bf_blob: bytes) -> tuple[int, int, bytes]:
    """Locate the inner BinaryFormatter blob inside ``bf_blob``.

    Returns ``(offset, length, decoded_bytes)`` where offset/length describe
    the base64 *string* span inside the outer blob (useful for patching
    back), and decoded_bytes is the decoded inner blob.
    """
    start = bf_blob.find(_INNER_BF_MARKER)
    if start < 0:
        raise ValueError("could not locate inner CS Dialogue Manager blob")
    end = start
    while end < len(bf_blob) and bf_blob[end] in _B64_ALPHABET:
        end += 1
    return start, end - start, base64.b64decode(bf_blob[start:end])


def find_lua_tag_stream(inner_bf: bytes) -> tuple[int, int]:
    """Find the embedded Lua tag stream inside the inner BF blob.

    Returns ``(offset, length)`` of the tag stream within ``inner_bf``.
    Heuristic: scan for the first ``S<len><printable>`` run; the stream
    runs from there to the end of the blob.
    """
    for i in range(len(inner_bf) - 4):
        if inner_bf[i] == 0x53:  # 'S' tag
            ln = inner_bf[i + 1]
            if 1 <= ln <= 100 and i + 2 + ln <= len(inner_bf):
                txt = inner_bf[i + 2 : i + 2 + ln]
                if all(0x20 <= b < 0x7F for b in txt):
                    return i, len(inner_bf) - i
    raise ValueError("could not locate Lua tag stream")


def parse_pairs(tag_stream: bytes) -> list[tuple[int, str, float]]:
    """Walk the tag stream and return ``(value_offset, last_key, value)``.

    ``value_offset`` is where the 8-byte double sits, so callers can patch
    it in place. Keys are *not* filtered here — that's the caller's job
    via :func:`list_numeric_pairs`.
    """
    pairs: list[tuple[int, str, float]] = []
    last_str: str | None = None
    i = 0
    n = len(tag_stream)
    while i < n:
        b = tag_stream[i]
        if b == 0x53:  # S string
            if i + 1 >= n:
                break
            ln = tag_stream[i + 1]
            if i + 2 + ln > n:
                break
            try:
                last_str = tag_stream[i + 2 : i + 2 + ln].decode("utf-8")
            except UnicodeDecodeError:
                last_str = None
            i += 2 + ln
        elif b == 0x4E:  # N number (8-byte LE double)
            if i + 9 > n:
                break
            val = struct.unpack("<d", tag_stream[i + 1 : i + 9])[0]
            if last_str is not None:
                pairs.append((i + 1, last_str, val))
            i += 9
        elif b == 0x42:  # B boolean (1 byte)
            i += 2
        else:
            i += 1
    return pairs


def list_numeric_pairs(bf_blob: bytes) -> list[tuple[str, float]]:
    """Return ``(key, value)`` for every numeric variable in the save.

    Filtered to identifier-shaped keys (see :data:`_VALID_KEY_RE`).
    """
    _, _, inner_bf = find_inner_base64(bf_blob)
    off, ln = find_lua_tag_stream(inner_bf)
    pairs = parse_pairs(inner_bf[off : off + ln])
    return [(k, v) for _, k, v in pairs if _VALID_KEY_RE.match(k)]


def set_value(bf_blob: bytes, key: str, new_value: float) -> tuple[bytes, float | None]:
    """Patch the first occurrence of ``key`` to ``new_value``.

    Returns ``(new_bf_blob, old_value)``. ``old_value`` is ``None`` if the
    key isn't found (and ``new_bf_blob`` is then returned unchanged).
    """
    inner_start, inner_len, inner_bf = find_inner_base64(bf_blob)
    tag_off, tag_len = find_lua_tag_stream(inner_bf)
    tag_stream = inner_bf[tag_off : tag_off + tag_len]

    for num_off, k, val in parse_pairs(tag_stream):
        if k != key:
            continue
        new_bytes = struct.pack("<d", float(new_value))
        new_tag_stream = tag_stream[:num_off] + new_bytes + tag_stream[num_off + 8 :]
        new_inner_bf = inner_bf[:tag_off] + new_tag_stream + inner_bf[tag_off + tag_len :]
        new_b64 = base64.b64encode(new_inner_bf)
        if len(new_b64) != inner_len:
            raise RuntimeError(
                f"internal size mismatch ({len(new_b64)} vs {inner_len}); refusing to save"
            )
        return bf_blob[:inner_start] + new_b64 + bf_blob[inner_start + inner_len :], val
    return bf_blob, None


def add_value(bf_blob: bytes, key: str, delta: float) -> tuple[bytes, float | None, float | None]:
    """Add ``delta`` to the current value of ``key``. Returns ``(new_bf, old, new)``."""
    _, _, inner_bf = find_inner_base64(bf_blob)
    off, ln = find_lua_tag_stream(inner_bf)
    for _, k, v in parse_pairs(inner_bf[off : off + ln]):
        if k == key:
            new_bf, old = set_value(bf_blob, key, v + float(delta))
            return new_bf, old, v + float(delta)
    return bf_blob, None, None
