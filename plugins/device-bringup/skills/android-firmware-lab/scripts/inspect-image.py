#!/usr/bin/env python3
"""Identify common Android firmware image formats without modifying them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from pathlib import Path


def read_at(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as image:
        image.seek(offset)
        return image.read(size)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image:
        for chunk in iter(lambda: image.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def u32le(data: bytes, offset: int) -> int | None:
    if len(data) < offset + 4:
        return None
    return struct.unpack_from("<I", data, offset)[0]


def detect(path: Path) -> dict[str, object]:
    size = path.stat().st_size
    head = read_at(path, 0, min(size, 4096))
    tail = read_at(path, max(0, size - 64), min(size, 64))
    formats: list[str] = []
    details: dict[str, object] = {}

    if head.startswith(b"ANDROID!"):
        formats.append("android-boot")
        details["boot_header_version"] = u32le(head, 40)
        details["kernel_size"] = u32le(head, 8)
        details["ramdisk_size"] = u32le(head, 16) if (u32le(head, 40) or 0) <= 2 else u32le(head, 12)
    if head.startswith(b"VNDRBOOT"):
        formats.append("android-vendor-boot")
        details["vendor_boot_header_version"] = u32le(head, 8)
        details["page_size"] = u32le(head, 12)
    if head.startswith(b"AVB0"):
        formats.append("avb-vbmeta")
    if len(tail) == 64 and tail.startswith(b"AVBf"):
        formats.append("avb-footer")
        _, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack(">4sIIQQQ28s", tail)
        details["avb_footer_version"] = f"{major}.{minor}"
        details["avb_original_image_size"] = original_size
        details["avb_vbmeta_offset"] = vbmeta_offset
        details["avb_vbmeta_size"] = vbmeta_size
    if head.startswith(b"CrAU"):
        formats.append("android-ota-payload")
    if len(head) >= 4 and struct.unpack_from("<I", head, 0)[0] == 0xED26FF3A:
        formats.append("android-sparse")
        details["sparse_major"] = struct.unpack_from("<H", head, 4)[0]
        details["sparse_minor"] = struct.unpack_from("<H", head, 6)[0]
        details["sparse_block_size"] = u32le(head, 12)
        details["sparse_total_blocks"] = u32le(head, 16)
    if len(head) >= 4 and struct.unpack_from(">I", head, 0)[0] == 0xD7B7AB1E:
        formats.append("android-dtbo-table")
    if head.startswith(b"PK\x03\x04"):
        formats.append("zip")
    if read_at(path, 1024, 4) == struct.pack("<I", 0xE0F5E1E2):
        formats.append("erofs")
    if read_at(path, 1080, 2) == struct.pack("<H", 0xEF53):
        formats.append("ext-family-filesystem")
    if not formats:
        formats.append("unknown")

    return {
        "path": os.fspath(path.resolve()),
        "size": size,
        "sha256": sha256(path),
        "formats": formats,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"not a file: {args.image}")

    indent = 2 if args.pretty else None
    print(json.dumps(detect(args.image), indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
