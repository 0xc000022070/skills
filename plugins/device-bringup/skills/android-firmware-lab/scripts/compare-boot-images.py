#!/usr/bin/env python3
"""Compare Android boot or recovery images after normalized unpacking."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import lzma
import os
import shlex
import shutil
import stat
import struct
import subprocess
import tempfile
from pathlib import Path

FILE_OPTIONS = {
    "--bootconfig",
    "--dtb",
    "--kernel",
    "--ramdisk",
    "--recovery_acpio",
    "--recovery_dtbo",
    "--second",
    "--vendor_bootconfig",
    "--vendor_ramdisk",
}


def parse_size(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid size: {value}") from error


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def avb_footer(path: Path) -> dict[str, int] | None:
    if path.stat().st_size < 64:
        return None
    with path.open("rb") as source:
        source.seek(-64, os.SEEK_END)
        footer = source.read(64)
    if not footer.startswith(b"AVBf"):
        return None
    _, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack(">4sIIQQQ28s", footer)
    return {
        "version_major": major,
        "version_minor": minor,
        "original_image_size": original_size,
        "vbmeta_offset": vbmeta_offset,
        "vbmeta_size": vbmeta_size,
    }


def run_unpack(image: Path, output: Path) -> tuple[list[str], dict[str, str]]:
    output.mkdir(parents=True, exist_ok=True)
    command = ["unpack_bootimg", "--boot_img", os.fspath(image), "--out", os.fspath(output), "--format=mkbootimg"]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"unpack_bootimg failed for {image}: {result.stderr.strip()}")
    tokens = shlex.split(result.stdout.strip())
    arguments: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        option = tokens[index]
        if option.startswith("--") and index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
            arguments[option] = tokens[index + 1]
            index += 2
        else:
            arguments[option] = "true"
            index += 1
    return tokens, arguments


def component_manifest(output: Path, arguments: dict[str, str]) -> dict[str, dict[str, object]]:
    components: dict[str, dict[str, object]] = {}
    for option in FILE_OPTIONS:
        value = arguments.get(option)
        if value is None:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = output / path.name
        if not path.is_file():
            candidates = list(output.glob(path.name))
            if not candidates:
                continue
            path = candidates[0]
        components[option] = {
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return components


def normalized_arguments(arguments: dict[str, str]) -> dict[str, str]:
    return {key: (Path(value).name if key in FILE_OPTIONS else value) for key, value in sorted(arguments.items())}


def decompress_ramdisk(path: Path) -> tuple[str, bytes]:
    data = path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        return "gzip", gzip.decompress(data)
    if data.startswith(b"\xfd7zXZ\x00"):
        return "xz", lzma.decompress(data)
    if data.startswith((b"\x04\x22\x4d\x18", b"\x02\x21\x4c\x18")):
        lz4 = shutil.which("lz4")
        if lz4 is None:
            raise RuntimeError("ramdisk uses LZ4 but lz4 is unavailable")
        result = subprocess.run([lz4, "-dc", os.fspath(path)], check=False, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"lz4 failed for {path}: {result.stderr.decode(errors='replace').strip()}")
        return "lz4", result.stdout
    if data.startswith((b"070701", b"070702")):
        return "cpio-newc", data
    raise RuntimeError(f"unsupported ramdisk compression: {path}")


def align4(offset: int) -> int:
    return (offset + 3) & ~3


def parse_newc(data: bytes) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset : offset + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise RuntimeError(f"invalid newc header at offset {offset}")
        fields = [int(header[position : position + 8], 16) for position in range(6, 110, 8)]
        mode, uid, gid, mtime, file_size, name_size = fields[1], fields[2], fields[3], fields[5], fields[6], fields[11]
        name_start = offset + 110
        name_end = name_start + name_size
        name = data[name_start : name_end - 1].decode(errors="surrogateescape")
        content_start = align4(name_end)
        content_end = content_start + file_size
        if content_end > len(data):
            raise RuntimeError(f"truncated newc entry: {name}")
        content = data[content_start:content_end]
        offset = align4(content_end)
        if name == "TRAILER!!!":
            break
        if stat.S_ISREG(mode):
            kind = "file"
        elif stat.S_ISDIR(mode):
            kind = "directory"
        elif stat.S_ISLNK(mode):
            kind = "symlink"
        elif stat.S_ISCHR(mode):
            kind = "char-device"
        elif stat.S_ISBLK(mode):
            kind = "block-device"
        elif stat.S_ISFIFO(mode):
            kind = "fifo"
        else:
            kind = "other"
        entry: dict[str, object] = {
            "kind": kind,
            "mode": f"{stat.S_IMODE(mode):04o}",
            "uid": uid,
            "gid": gid,
            "mtime": mtime,
            "size": file_size,
        }
        if kind == "file":
            entry["sha256"] = sha256_bytes(content)
        elif kind == "symlink":
            entry["target"] = content.decode(errors="surrogateescape")
        entries[name] = entry
    return entries


def ramdisk_manifest(output: Path, arguments: dict[str, str]) -> tuple[str, dict[str, dict[str, object]]] | None:
    value = arguments.get("--ramdisk") or arguments.get("--vendor_ramdisk")
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = output / path.name
    if not path.is_file():
        candidates = list(output.glob(path.name))
        if not candidates:
            return None
        path = candidates[0]
    compression, archive = decompress_ramdisk(path)
    return compression, parse_newc(archive)


def diff_mapping(stock: dict[str, object], candidate: dict[str, object], limit: int) -> dict[str, object]:
    stock_keys = set(stock)
    candidate_keys = set(candidate)
    added = sorted(candidate_keys - stock_keys)
    removed = sorted(stock_keys - candidate_keys)
    changed = sorted(key for key in stock_keys & candidate_keys if stock[key] != candidate[key])
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added[:limit],
        "removed": removed[:limit],
        "changed": changed[:limit],
        "truncated": any(len(values) > limit for values in (added, removed, changed)),
    }


def normalized_entries(entries: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        path: {key: value for key, value in entry.items() if key != "mtime"}
        for path, entry in entries.items()
    }


def scan_tokens(entries: dict[str, dict[str, object]], output: Path, arguments: dict[str, str], tokens: list[str]) -> dict[str, list[str]]:
    matches = {token: [] for token in tokens}
    value = arguments.get("--ramdisk") or arguments.get("--vendor_ramdisk")
    if value is None:
        return matches
    ramdisk_path = Path(value)
    if not ramdisk_path.is_absolute():
        ramdisk_path = output / ramdisk_path.name
    _, archive = decompress_ramdisk(ramdisk_path)
    offset = 0
    while offset + 110 <= len(archive):
        header = archive[offset : offset + 110]
        if header[:6] not in (b"070701", b"070702"):
            break
        fields = [int(header[position : position + 8], 16) for position in range(6, 110, 8)]
        file_size, name_size = fields[6], fields[11]
        name_start = offset + 110
        name_end = name_start + name_size
        name = archive[name_start : name_end - 1].decode(errors="surrogateescape")
        content_start = align4(name_end)
        content_end = content_start + file_size
        content = archive[content_start:content_end]
        offset = align4(content_end)
        if name == "TRAILER!!!":
            break
        if entries.get(name, {}).get("kind") != "file" or b"\x00" in content[:8192]:
            continue
        text = content.decode(errors="replace").casefold()
        for token in tokens:
            if token.casefold() in text:
                matches[token].append(name)
    return matches


def inspect_image(path: Path, output: Path) -> dict[str, object]:
    _, arguments = run_unpack(path, output)
    ramdisk = ramdisk_manifest(output, arguments)
    return {
        "path": os.fspath(path.resolve()),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "avb_footer": avb_footer(path),
        "mkbootimg_arguments": normalized_arguments(arguments),
        "components": component_manifest(output, arguments),
        "ramdisk_compression": ramdisk[0] if ramdisk else None,
        "ramdisk_entries": ramdisk[1] if ramdisk else {},
        "_arguments": arguments,
        "_output": output,
    }


def public_image(image: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in image.items() if not key.startswith("_") and key != "ramdisk_entries"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--partition-size", type=parse_size)
    parser.add_argument("--expected", action="append", default=[], help="token expected somewhere in the candidate ramdisk")
    parser.add_argument("--forbid", action="append", default=[], help="token forbidden in the candidate ramdisk")
    parser.add_argument("--max-diffs", type=int, default=200)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    for image in (args.stock, args.candidate):
        if not image.is_file():
            parser.error(f"not a file: {image}")
    if shutil.which("unpack_bootimg") is None:
        parser.error("unpack_bootimg is required")

    with tempfile.TemporaryDirectory(prefix="android-boot-compare-") as temporary:
        root = Path(temporary)
        stock = inspect_image(args.stock, root / "stock")
        candidate = inspect_image(args.candidate, root / "candidate")
        stock_entries = stock["ramdisk_entries"]
        candidate_entries = candidate["ramdisk_entries"]
        common_entries = set(stock_entries) & set(candidate_entries)
        mtime_changed = sum(
            stock_entries[path].get("mtime") != candidate_entries[path].get("mtime")
            for path in common_entries
        )
        token_matches = scan_tokens(candidate_entries, candidate["_output"], candidate["_arguments"], args.expected + args.forbid)
        findings: list[dict[str, str]] = []
        for token in args.expected:
            if not token_matches[token]:
                findings.append({"severity": "warning", "code": "expected-token-absent", "message": token})
        for token in args.forbid:
            if token_matches[token]:
                findings.append({"severity": "error", "code": "forbidden-token-present", "message": token})
        if args.partition_size is not None and args.candidate.stat().st_size > args.partition_size:
            findings.append({"severity": "error", "code": "partition-overflow", "message": str(args.partition_size)})

        result = {
            "stock": public_image(stock),
            "candidate": public_image(candidate),
            "partition_size": args.partition_size,
            "candidate_partition_remaining": args.partition_size - args.candidate.stat().st_size if args.partition_size is not None else None,
            "header_diff": diff_mapping(stock["mkbootimg_arguments"], candidate["mkbootimg_arguments"], args.max_diffs),
            "component_diff": diff_mapping(stock["components"], candidate["components"], args.max_diffs),
            "ramdisk_diff": diff_mapping(normalized_entries(stock_entries), normalized_entries(candidate_entries), args.max_diffs),
            "ramdisk_mtime_changed_count": mtime_changed,
            "candidate_token_matches": token_matches,
            "findings": findings,
        }
        print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
        return 1 if any(item["severity"] == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
