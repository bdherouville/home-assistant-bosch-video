"""Fail when publication candidates contain local deployment information."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".storage",
    ".venv",
    "__pycache__",
    "tmp",
    "venv",
}
SKIP_FILES = {"env.txt", "secrets.yaml"}
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

FORBIDDEN_PATTERNS = {
    "private IPv4 address": re.compile(
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3})\b"
    ),
    "Windows user path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
    "deployment name": re.compile("les" + "guillaumes", re.IGNORECASE),
    "Telegram bot name": re.compile(r"@[A-Za-z0-9_]+_bot\b"),
    "Telegram bot token": re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
}
GENERIC_ENV_VALUES = {"service", "user", "live", "admin", "true", "false"}


def iter_public_files() -> Iterator[Path]:
    """Yield text files that may be published."""
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if path.name in SKIP_FILES or path.name.startswith(".env"):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {
            ".gitignore",
            "LICENSE",
        }:
            yield path


def local_secret_values() -> list[str]:
    """Read local secret values without returning their keys or printing them."""
    env_file = ROOT / "env.txt"
    if not env_file.exists():
        return []
    values: list[str] = []
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        value = line.split("=", 1)[1].strip().strip("'\"")
        if len(value) >= 8 and value.lower() not in GENERIC_ENV_VALUES:
            values.append(value)
    return values


def audit() -> list[str]:
    """Return privacy violations without including any secret value."""
    violations: list[str] = []
    secrets = local_secret_values()
    for path in iter_public_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for label, pattern in FORBIDDEN_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{relative}:{line}: {label}")
        for secret in secrets:
            if secret not in text:
                continue
            line = text.count("\n", 0, text.index(secret)) + 1
            violations.append(f"{relative}:{line}: value copied from local env")
    return violations


def main() -> int:
    """Run the command-line audit."""
    violations = audit()
    if violations:
        print("Publication privacy audit failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Publication privacy audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
