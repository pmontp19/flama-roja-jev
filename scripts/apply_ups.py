from __future__ import annotations

import sys
import zlib
from pathlib import Path


def _decode_ups_number(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 1
    while True:
        byte = data[pos]
        pos += 1
        result += (byte & 0x7F) * shift
        if byte & 0x80:
            break
        shift <<= 7
        result += shift
    return result, pos


def apply_ups(patch_path: str | Path, input_path: str | Path, output_path: str | Path) -> None:
    patch = Path(patch_path).read_bytes()
    source = Path(input_path).read_bytes()
    if patch[:4] != b"UPS1":
        raise SystemExit("no es un patch UPS valid")

    crc_in = int.from_bytes(patch[-12:-8], "little")
    crc_out = int.from_bytes(patch[-8:-4], "little")
    if zlib.crc32(source) & 0xFFFFFFFF != crc_in:
        raise SystemExit("la ROM base no es la que espera el patch (crc input mismatch)")

    pos = 4
    src_size, pos = _decode_ups_number(patch, pos)
    tgt_size, pos = _decode_ups_number(patch, pos)
    if len(source) != src_size:
        raise SystemExit(f"mida inesperada: {len(source)} vs {src_size}")

    target = bytearray(source)
    if tgt_size > len(target):
        target += bytearray(tgt_size - len(target))
    elif tgt_size < len(target):
        target = target[:tgt_size]

    footer = len(patch) - 12
    out_pos = 0
    while pos < footer:
        offset, pos = _decode_ups_number(patch, pos)
        out_pos += offset
        while pos < footer and patch[pos] != 0:
            if out_pos < len(target):
                target[out_pos] ^= patch[pos]
            out_pos += 1
            pos += 1
        pos += 1
        out_pos += 1

    if zlib.crc32(bytes(target)) & 0xFFFFFFFF != crc_out:
        raise SystemExit("el resultat no quadra amb el crc esperat del patch")
    Path(output_path).write_bytes(bytes(target))
    print("crc input ok | crc output ok")
    print(f"parchejat: {output_path} ({len(target)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("us: python apply_ups.py <patch.ups> <rom_base.gba> <sortida.gba>")
    apply_ups(sys.argv[1], sys.argv[2], sys.argv[3])
