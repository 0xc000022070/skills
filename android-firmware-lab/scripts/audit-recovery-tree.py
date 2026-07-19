#!/usr/bin/env python3
"""Audit an Android recovery device tree for identity and provenance risks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

SKIP_PARTS = {".git", ".repo", "artifacts", "inspection", "out"}
IDENTITY_PATTERNS = (
    re.compile(
        r"(?:PRODUCT_DEVICE|TARGET_DEVICE|TARGET_BOOTLOADER_BOARD_NAME|"
        r"ro(?:\.product(?:\.[a-z0-9_]+)?)?\.device|ro\.build\.product)"
        r"\s*(?::=|\+=|=)\s*[\"']?([A-Za-z0-9_.-]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:PRODUCT_MODEL|ro(?:\.product(?:\.[a-z0-9_]+)?)?\.model)\s*(?::=|\+=|=)\s*[\"']?([A-Za-z0-9_.-]+)", re.IGNORECASE),
)
RISK_PATTERNS = (
    ("selinux-permissive", re.compile(r"androidboot\.selinux=permissive|setenforce\s+0", re.IGNORECASE), "SELinux is forced permissive"),
    ("test-avb-key", re.compile(r"external/avb/test/data|testkey_rsa", re.IGNORECASE), "AOSP test AVB key is configured"),
    ("source-mutation", re.compile(r"\bsed\s+-i\b|\bperl\s+-pi\b"), "build script mutates source files"),
    ("disabled-errors", re.compile(r"\bset\s+\+[eu]\b"), "build script disables shell error checking"),
    ("missing-dependencies", re.compile(r"ALLOW_MISSING_DEPENDENCIES\s*(?::=|=)\s*true", re.IGNORECASE), "missing dependencies are allowed"),
    ("input-workaround", re.compile(r"TW_IGNORE_(?:MAJOR_AXIS_0|MT_POSITION_0|ABS_MT_TRACKING_ID)\s*(?::=|=)\s*true"), "TWRP input semantics are overridden"),
    ("hardcoded-udc", re.compile(r"(?:sys\.usb\.controller|vendor\.usb\.controller)\s+[^$\s][^\s]*|/UDC\s+(?![\"']?none[\"']?(?:\s|$))[\"']?[^$\s]", re.IGNORECASE), "USB controller or UDC appears hard-coded"),
)


def parse_size(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid size: {value}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(tree: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(tree), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def text_files(tree: Path) -> list[Path]:
    paths: list[Path] = []
    for path in tree.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.relative_to(tree).parts):
            continue
        try:
            sample = path.read_bytes()[:8192]
        except OSError:
            continue
        if b"\x00" not in sample:
            paths.append(path)
    return sorted(paths)


def issue(severity: str, code: str, message: str, path: Path | None = None, line: int | None = None) -> dict[str, object]:
    result: dict[str, object] = {"severity": severity, "code": code, "message": message}
    if path is not None:
        result["path"] = os.fspath(path)
    if line is not None:
        result["line"] = line
    return result


def expected_twrp_branch(launch_android: int) -> str | None:
    if launch_android >= 12:
        return "12.1"
    if launch_android >= 10:
        return "11"
    if launch_android == 9:
        return "9"
    if launch_android >= 7:
        return "8.1"
    if launch_android >= 5:
        return "6"
    return None


def audit(args: argparse.Namespace) -> dict[str, object]:
    tree = args.tree.resolve()
    expected = {value.casefold() for value in args.expected}
    forbidden = {value.casefold() for value in args.forbid}
    issues: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    branch_mentions: set[str] = set()
    scanned = text_files(tree)

    for path in scanned:
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        relative = path.relative_to(tree)
        operational = path.suffix.casefold() not in {".md", ".txt"}
        for line_number, line_text in enumerate(content.splitlines(), 1):
            folded = line_text.casefold()
            if operational:
                for pattern in IDENTITY_PATTERNS:
                    for match in pattern.finditer(line_text):
                        value = match.group(1)
                        identities.append({"value": value, "path": os.fspath(relative), "line": line_number})
                        if expected and value.casefold() not in expected:
                            issues.append(issue("error", "unexpected-identity", f"identity value is not allowlisted: {value}", relative, line_number))
                validator_line = re.search(r"\b(?:grep|rg)\b", line_text) is not None
                for token in forbidden:
                    if token in folded and not validator_line:
                        issues.append(issue("error", "forbidden-identity", f"forbidden token found: {token}", relative, line_number))
                for code, pattern, message in RISK_PATTERNS:
                    if pattern.search(line_text):
                        issues.append(issue("warning", code, message, relative, line_number))
            for match in re.finditer(r"(?:twrp|android)[\s_-]?(6|8\.1|9|11|12\.1)", line_text, re.IGNORECASE):
                branch_mentions.add(match.group(1))

    expected_branch = expected_twrp_branch(args.launch_android) if args.launch_android is not None else None
    if expected_branch and branch_mentions and expected_branch not in branch_mentions:
        issues.append(
            issue(
                "warning",
                "twrp-branch-mismatch",
                f"launch Android {args.launch_android} maps to TWRP {expected_branch} in the reviewed TeamWin matrix; found {sorted(branch_mentions)}",
            )
        )

    prebuilt_hashes: list[dict[str, object]] = []
    prebuilt_dir = tree / "prebuilt"
    if prebuilt_dir.is_dir():
        for path in sorted(item for item in prebuilt_dir.rglob("*") if item.is_file()):
            prebuilt_hashes.append(
                {
                    "path": os.fspath(path.relative_to(tree)),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
        provenance_files = [
            path
            for path in tree.rglob("*")
            if path.is_file() and ("provenance" in path.name.casefold() or path.name.startswith("SHA256SUMS"))
        ]
        if prebuilt_hashes and not provenance_files:
            issues.append(issue("warning", "missing-prebuilt-provenance", "prebuilt files exist without a provenance or SHA256SUMS record"))

    image: dict[str, object] | None = None
    if args.candidate_image is not None:
        candidate = args.candidate_image.resolve()
        image = {"path": os.fspath(candidate), "size": candidate.stat().st_size, "sha256": sha256(candidate)}
        if args.partition_size is not None:
            image["partition_size"] = args.partition_size
            image["remaining"] = args.partition_size - candidate.stat().st_size
            if candidate.stat().st_size > args.partition_size:
                issues.append(issue("error", "partition-overflow", "candidate image exceeds the declared partition size"))

    dirty = git_value(tree, "status", "--porcelain")
    git_data = {
        "remote": git_value(tree, "remote", "get-url", "origin"),
        "head": git_value(tree, "rev-parse", "HEAD"),
        "branch": git_value(tree, "branch", "--show-current"),
        "dirty": bool(dirty),
        "status": dirty.splitlines() if dirty else [],
    }
    if git_data["dirty"]:
        issues.append(issue("warning", "dirty-tree", "device tree contains uncommitted or untracked build inputs"))

    return {
        "tree": os.fspath(tree),
        "git": git_data,
        "expected_identities": sorted(expected),
        "forbidden_identities": sorted(forbidden),
        "identity_assignments": identities,
        "branch_mentions": sorted(branch_mentions),
        "prebuilt_files": prebuilt_hashes,
        "candidate_image": image,
        "scanned_text_files": len(scanned),
        "issues": issues,
        "summary": {
            "errors": sum(item["severity"] == "error" for item in issues),
            "warnings": sum(item["severity"] == "warning" for item in issues),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("--expected", action="append", default=[], help="allowlisted device, board, model, SoC, or hardware identity")
    parser.add_argument("--forbid", action="append", default=[], help="known donor or sibling identity that must not appear")
    parser.add_argument("--launch-android", type=int)
    parser.add_argument("--candidate-image", type=Path)
    parser.add_argument("--partition-size", type=parse_size)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if not args.tree.is_dir():
        parser.error(f"not a directory: {args.tree}")
    if args.candidate_image is not None and not args.candidate_image.is_file():
        parser.error(f"not a file: {args.candidate_image}")
    if args.partition_size is not None and args.candidate_image is None:
        parser.error("--partition-size requires --candidate-image")

    result = audit(args)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if result["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
