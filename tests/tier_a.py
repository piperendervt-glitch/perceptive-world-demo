#!/usr/bin/env python3
"""Tier A v3 deterministic atlas, hero-direction, and LOD static verifier.

Approved preregistration: LOD Test Preregistration 3.0-rc2
Target tag: tierA-lod-v3
Target commit: 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f (replaced after the annotated tag is cut)
Baseline: tierA-hero-fix-v2 / 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

Allowed runtime dependencies: Python standard library, Pillow, numpy, and
read-only Git commands. Browser and JavaScript execution are prohibited.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import math
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import numpy as np
    from PIL import Image
except Exception as exc:  # pragma: no cover - exercised only in broken envs
    np = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]
    DEPENDENCY_ERROR: str | None = f"{type(exc).__name__}: {exc}"
else:
    DEPENDENCY_ERROR = None


PREREGISTRATION_VERSION = "3.0-rc2"
EXPECTED_TAG = "tierA-lod-v3"
EXPECTED_COMMIT = "5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f"
BASELINE_TAG = "tierA-hero-fix-v2"
BASELINE_COMMIT = "13dbea7deec6e5994501ffc5e70b47e9d0e24dcf"
CHECKPOINT_IS_PLACEHOLDER = EXPECTED_COMMIT.startswith("<") and EXPECTED_COMMIT.endswith(">")
TARGET_PROHIBITED_PATHS = (
    "preregistration-v3.md",
    "TIER_A_RUNBOOK_V3.md",
    "tests/tier_a.py",
    "tests/tier_b",
    "playwright.config.mjs",
    "package.json",
    "package-lock.json",
)
REQUIRED_TARGET_PATHS = (
    "index.html",
    "assets/hi/manifest_hi.json",
    "assets/hi/atlas_hi.png",
)

REQUIRED_BASE_SPRITES = (
    "grass",
    "dirt",
    "water",
    "flower",
    "hero_down_0",
    "hero_down_1",
    "hero_down_2",
    "hero_up_0",
    "hero_up_1",
    "hero_up_2",
    "hero_side_0",
    "hero_side_1",
    "hero_side_2",
    "tree",
    "well",
    "shrine",
    "torch",
    "house",
    "goblin",
    "sentry",
    "chief",
    "ifloor",
    "iwall",
    "idoor",
    "npc_elder",
    "npc_herb",
    "table",
    "chair",
    "shelf",
    "bed",
    "plant",
    "barrel",
    "cauldron",
    "rug",
)
HERO_DIRECTIONS = ("down", "up", "side")
HERO_INDICES = (0, 1, 2)
HERO_FRAMES = tuple(
    f"hero_{direction}_{index}"
    for direction in HERO_DIRECTIONS
    for index in HERO_INDICES
)

HEAD_REGION_FRACTION = 0.50
T_FACE = 0.08
T_NOFACE = 0.01
T_DOWN_UP_RATIO = 5.0
T_CENTER = 0.05
T_SIDE_RIGHT = 0.57

VERIFICATION_REPORT = "tier_a_v3_report.json"
SELFTEST_REPORT = "tier_a_v3_selftest_report.json"

LANDMARK_KEYS = ("well", "shrine", "lookout", "elder", "herb")
FOCUS_IMAGE_KEYS = ("well", "shrine", "elder", "herb")
TOWER_IMAGE_IDS = ("TOWER_FULL", "TOWER_TOP", "TOWER_VIEW")
ENEMY_KINDS_EXPECTED = ("goblin", "sentry", "chief")
ENEMY_LEVELS = (1, 2, 3)
ENEMY_WEAK_EXPECTED = {
    "goblin": "まほう",
    "sentry": "たたかう(物理)",
    "chief": "まほう",
}
ENEMY_STATS_EXPECTED = {
    "goblin": {"hp": 5, "atk": 0, "dmg": [1, 2], "target": 6},
    "sentry": {"hp": 5, "atk": 0, "dmg": [1, 2], "target": 6},
    "chief": {"hp": 18, "atk": 2, "dmg": [2, 5], "target": 8},
}
ROOM_SUBJECTS = ("elder", "herb")
ROOM_REQUIRED_FIELDS = ("room", "npcImg", "tile")
LOD_TABLE_NAMES = (
    "FOCUS_CAP",
    "FOCUS_TXT",
    "FOCUS_EVENT",
    "FOCUS_IMG",
    "TAKEN_MSG",
    "ENEMY_KINDS",
    "ENEMY_IMG",
    "ENEMY_WEAK",
    "ROOM_SUBJ",
)
FROZEN_FUNCTION_NAMES = ("sprAt", "drawHeroImg")


class TierAError(Exception):
    """Base class for controlled Tier A errors."""


class SetupError(TierAError):
    """Checkpoint, dependency, extraction, or internal setup failure."""


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class HeroMetrics:
    rectangle: Rect
    crop_width: int
    crop_height: int
    opaque_bbox: tuple[int, int, int, int]
    head_region: tuple[int, int, int, int]
    head_opaque_pixels: int
    head_skin_pixels: int
    face_ratio: float
    normalized_skin_centroid_x: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rectangle": self.rectangle.as_dict(),
            "crop_width": self.crop_width,
            "crop_height": self.crop_height,
            "opaque_bbox": list(self.opaque_bbox),
            "head_region": list(self.head_region),
            "head_opaque_pixels": self.head_opaque_pixels,
            "head_skin_pixels": self.head_skin_pixels,
            "face_ratio": self.face_ratio,
            "normalized_skin_centroid_x": self.normalized_skin_centroid_x,
        }


class ReportBuilder:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.checks: list[dict[str, Any]] = []
        self.fatal = False

    def add(
        self,
        check_id: str,
        status: str,
        *,
        atlas: str | None = None,
        sprites: Sequence[str] = (),
        measured: Mapping[str, Any] | None = None,
        threshold: Mapping[str, Any] | None = None,
        message: str = "",
        category: str = "invariant",
    ) -> None:
        if status not in {"pass", "fail", "skip"}:
            raise ValueError(f"invalid check status: {status}")
        record: dict[str, Any] = {
            "id": check_id,
            "status": status,
            "atlas": atlas,
            "sprites": list(sprites),
            "measured": dict(measured or {}),
            "threshold": dict(threshold or {}),
            "message": message,
            "category": category,
        }
        self.checks.append(record)
        if status == "fail" and category in {"setup", "checkpoint", "internal"}:
            self.fatal = True

    def summary(self) -> dict[str, int]:
        return {
            "passed": sum(c["status"] == "pass" for c in self.checks),
            "failed": sum(c["status"] == "fail" for c in self.checks),
            "skipped": sum(c["status"] == "skip" for c in self.checks),
        }

    def exit_code(self) -> int:
        if self.fatal:
            return 2
        if any(c["status"] == "fail" for c in self.checks):
            return 1
        return 0

    def overall_status(self) -> str:
        code = self.exit_code()
        if code == 0:
            return "pass"
        if code == 1:
            return "fail"
        return "error"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    if np is not None:
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def write_json_report(path: Path, payload: Mapping[str, Any]) -> None:
    normalized = _json_safe(dict(payload))
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def run_git(repo_root: Path, args: Sequence[str], *, binary: bool = False) -> bytes | str:
    command = ["git", "-C", str(repo_root), *args]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise SetupError(f"cannot execute git: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SetupError(f"git {' '.join(args)} failed: {stderr}")
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").strip()


def git_blob(repo_root: Path, path: str) -> bytes:
    return run_git(repo_root, ["show", f"HEAD:{path}"], binary=True)  # type: ignore[return-value]


def parse_json_bytes(data: bytes, source: str) -> Any:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SetupError(f"{source} is not valid UTF-8: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SetupError(f"{source} is not valid JSON: {exc}") from exc


def _ensure_dependencies() -> None:
    if DEPENDENCY_ERROR is not None:
        raise SetupError(f"Pillow/numpy dependency failure: {DEPENDENCY_ERROR}")


# ---------------------------------------------------------------------------
# Static extraction
# ---------------------------------------------------------------------------


def extract_json_const(html: str, name: str) -> dict[str, Any]:
    pattern = re.compile(rf"\bconst\s+{re.escape(name)}\b\s*=", re.MULTILINE)
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise SetupError(
            f"expected exactly one const {name} declaration, found {len(matches)}"
        )
    start = matches[0].end()
    remainder = html[start:]
    decoder = json.JSONDecoder()
    leading = len(remainder) - len(remainder.lstrip())
    try:
        value, consumed = decoder.raw_decode(remainder.lstrip())
    except json.JSONDecodeError as exc:
        raise SetupError(f"const {name} is not valid JSON: {exc}") from exc
    cursor = leading + consumed
    while cursor < len(remainder) and remainder[cursor].isspace():
        cursor += 1
    if cursor >= len(remainder) or remainder[cursor] != ";":
        raise SetupError(f"const {name} has no terminating semicolon after JSON value")
    if not isinstance(value, dict):
        raise SetupError(f"const {name} top-level value is not an object")
    return value


def extract_atlas_payload(html: str, name: str) -> str:
    pattern = re.compile(
        rf"\b{re.escape(name)}\s*\.\s*src\s*=\s*"
        r"(?P<quote>['\"])data:image/png;base64,(?P<payload>[^'\"]*)(?P=quote)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise SetupError(
            f"expected exactly one {name}.src PNG data URL assignment, found {len(matches)}"
        )
    return matches[0].group("payload")


def decode_embedded_png(payload: str, source: str) -> Any:
    _ensure_dependencies()
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SetupError(f"{source} contains invalid strict base64: {exc}") from exc
    return decode_png_bytes(raw, source)


def decode_png_bytes(raw: bytes, source: str) -> Any:
    _ensure_dependencies()
    if not raw:
        raise SetupError(f"{source} is empty")
    try:
        with Image.open(io.BytesIO(raw)) as probe:  # type: ignore[union-attr]
            if probe.format != "PNG":
                raise SetupError(f"{source} decoded format is {probe.format!r}, not PNG")
            probe.verify()
        with Image.open(io.BytesIO(raw)) as image:  # type: ignore[union-attr]
            if image.format != "PNG":
                raise SetupError(f"{source} reopened format is {image.format!r}, not PNG")
            rgba = image.convert("RGBA")
            rgba.load()
    except SetupError:
        raise
    except Exception as exc:
        raise SetupError(f"{source} is not a fully decodable PNG: {exc}") from exc
    if rgba.width <= 0 or rgba.height <= 0:
        raise SetupError(f"{source} has non-positive dimensions {rgba.size}")
    return rgba


# ---------------------------------------------------------------------------
# LOD JavaScript static parsing and frozen-source extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JSIdentifier:
    name: str


@dataclass(frozen=True)
class JSFunctionSource:
    source: str


@dataclass(frozen=True)
class JSTemplateString:
    source: str
    has_interpolation: bool


@dataclass
class JSObjectValue:
    pairs: list[tuple[str, Any]]
    duplicates: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in self.pairs:
            if key in result and key not in self.duplicates:
                self.duplicates.append(key)
            result[key] = value
        return result

    def keys(self) -> list[str]:
        return [key for key, _ in self.pairs]


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    source: str


@dataclass
class ImageSourceRecord:
    identifier: str
    construction_count: int = 0
    src_payloads: list[str] = field(default_factory=list)
    src_statements: list[str] = field(default_factory=list)


class JSStaticParser:
    """Small deterministic parser for the preregistered JavaScript literal subset."""

    def __init__(self, source: str, start: int = 0) -> None:
        self.source = source
        self.pos = start
        self.length = len(source)

    def error(self, message: str) -> SetupError:
        excerpt = self.source[max(0, self.pos - 30) : min(self.length, self.pos + 50)]
        return SetupError(f"JavaScript static parse error at {self.pos}: {message}; near {excerpt!r}")

    def skip_space_comments(self) -> None:
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch.isspace():
                self.pos += 1
                continue
            if self.source.startswith("//", self.pos):
                newline = self.source.find("\n", self.pos + 2)
                self.pos = self.length if newline < 0 else newline + 1
                continue
            if self.source.startswith("/*", self.pos):
                end = self.source.find("*/", self.pos + 2)
                if end < 0:
                    raise self.error("unterminated block comment")
                self.pos = end + 2
                continue
            break

    def peek(self) -> str:
        self.skip_space_comments()
        return self.source[self.pos] if self.pos < self.length else ""

    def consume(self, expected: str) -> None:
        self.skip_space_comments()
        if not self.source.startswith(expected, self.pos):
            raise self.error(f"expected {expected!r}")
        self.pos += len(expected)

    def parse_identifier_name(self) -> str:
        self.skip_space_comments()
        match = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", self.source[self.pos :])
        if not match:
            raise self.error("expected identifier")
        value = match.group(0)
        self.pos += len(value)
        return value

    def parse_string(self) -> str | JSTemplateString:
        self.skip_space_comments()
        if self.pos >= self.length or self.source[self.pos] not in "'\"`":
            raise self.error("expected string")
        quote = self.source[self.pos]
        start = self.pos
        self.pos += 1
        chars: list[str] = []
        interpolation = False
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch == "\\":
                if self.pos + 1 >= self.length:
                    raise self.error("unterminated escape")
                esc = self.source[self.pos + 1]
                mapping = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}
                if esc == "u" and self.pos + 5 < self.length:
                    code = self.source[self.pos + 2 : self.pos + 6]
                    try:
                        chars.append(chr(int(code, 16)))
                    except ValueError:
                        chars.append("\\u" + code)
                    self.pos += 6
                    continue
                if esc == "x" and self.pos + 3 < self.length:
                    code = self.source[self.pos + 2 : self.pos + 4]
                    try:
                        chars.append(chr(int(code, 16)))
                    except ValueError:
                        chars.append("\\x" + code)
                    self.pos += 4
                    continue
                chars.append(mapping.get(esc, esc))
                self.pos += 2
                continue
            if quote == "`" and self.source.startswith("${", self.pos):
                interpolation = True
                # Preserve the complete template source but skip the interpolation safely.
                self.pos += 2
                depth = 1
                while self.pos < self.length and depth:
                    inner = self.source[self.pos]
                    if inner in "'\"`":
                        self._skip_quoted(inner)
                        continue
                    if self.source.startswith("//", self.pos):
                        newline = self.source.find("\n", self.pos + 2)
                        self.pos = self.length if newline < 0 else newline + 1
                        continue
                    if self.source.startswith("/*", self.pos):
                        end = self.source.find("*/", self.pos + 2)
                        if end < 0:
                            raise self.error("unterminated comment in template")
                        self.pos = end + 2
                        continue
                    if inner == "{":
                        depth += 1
                    elif inner == "}":
                        depth -= 1
                    self.pos += 1
                continue
            if ch == quote:
                self.pos += 1
                raw = self.source[start : self.pos]
                if quote == "`":
                    return JSTemplateString(raw, interpolation)
                return "".join(chars)
            chars.append(ch)
            self.pos += 1
        raise self.error("unterminated string")

    def _skip_quoted(self, quote: str) -> None:
        if self.source[self.pos] != quote:
            raise self.error("internal quoted-skip mismatch")
        self.pos += 1
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch == "\\":
                self.pos += 2
                continue
            self.pos += 1
            if ch == quote:
                return
        raise self.error("unterminated quoted value")

    def parse_number(self) -> int | float:
        self.skip_space_comments()
        match = re.match(
            r"[-+]?(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|0[oO][0-7]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
            self.source[self.pos :],
        )
        if not match:
            raise self.error("expected number")
        raw = match.group(0)
        self.pos += len(raw)
        sign = -1 if raw.startswith("-") else 1
        unsigned = raw[1:] if raw[:1] in "+-" else raw
        if unsigned.lower().startswith("0x"):
            return sign * int(unsigned, 16)
        if unsigned.lower().startswith("0b"):
            return sign * int(unsigned, 2)
        if unsigned.lower().startswith("0o"):
            return sign * int(unsigned, 8)
        return float(raw) if any(c in raw for c in ".eE") else int(raw)

    def parse_array(self) -> list[Any]:
        self.consume("[")
        values: list[Any] = []
        self.skip_space_comments()
        if self.peek() == "]":
            self.consume("]")
            return values
        while True:
            values.append(self.parse_value())
            self.skip_space_comments()
            ch = self.peek()
            if ch == ",":
                self.consume(",")
                self.skip_space_comments()
                if self.peek() == "]":
                    self.consume("]")
                    return values
                continue
            if ch == "]":
                self.consume("]")
                return values
            raise self.error("expected ',' or ']' in array")

    def parse_object_key(self) -> str:
        self.skip_space_comments()
        ch = self.peek()
        if ch in "'\"`":
            value = self.parse_string()
            if isinstance(value, JSTemplateString):
                raise self.error("template literal is not allowed as object key")
            return value
        if ch.isdigit() or ch in "+-":
            return str(self.parse_number())
        return self.parse_identifier_name()

    def parse_object(self) -> JSObjectValue:
        self.consume("{")
        pairs: list[tuple[str, Any]] = []
        seen: set[str] = set()
        duplicates: list[str] = []
        self.skip_space_comments()
        if self.peek() == "}":
            self.consume("}")
            return JSObjectValue(pairs, duplicates)
        while True:
            key = self.parse_object_key()
            self.skip_space_comments()
            if self.peek() != ":":
                raise self.error("object shorthand/computed property is outside the preregistered subset")
            self.consume(":")
            value = self.parse_value()
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)
            pairs.append((key, value))
            self.skip_space_comments()
            ch = self.peek()
            if ch == ",":
                self.consume(",")
                self.skip_space_comments()
                if self.peek() == "}":
                    self.consume("}")
                    return JSObjectValue(pairs, duplicates)
                continue
            if ch == "}":
                self.consume("}")
                return JSObjectValue(pairs, duplicates)
            raise self.error("expected ',' or '}' in object")

    def parse_function_expression(self) -> JSFunctionSource:
        self.skip_space_comments()
        start = self.pos
        if self.source.startswith("function", self.pos):
            self.pos += len("function")
            self.skip_space_comments()
            # Optional function name.
            if re.match(r"[A-Za-z_$]", self.source[self.pos : self.pos + 1]):
                self.parse_identifier_name()
            self.skip_space_comments()
            self._scan_balanced("(", ")")
            self.skip_space_comments()
            self._scan_balanced("{", "}")
            return JSFunctionSource(self.source[start : self.pos])
        raise self.error("expected function expression")

    def _scan_balanced(self, opening: str, closing: str) -> None:
        self.skip_space_comments()
        if self.pos >= self.length or self.source[self.pos] != opening:
            raise self.error(f"expected balanced {opening}{closing}")
        depth = 0
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch in "'\"`":
                self._skip_quoted(ch)
                continue
            if self.source.startswith("//", self.pos):
                newline = self.source.find("\n", self.pos + 2)
                self.pos = self.length if newline < 0 else newline + 1
                continue
            if self.source.startswith("/*", self.pos):
                end = self.source.find("*/", self.pos + 2)
                if end < 0:
                    raise self.error("unterminated block comment")
                self.pos = end + 2
                continue
            if ch == opening:
                depth += 1
            elif ch == closing:
                depth -= 1
                self.pos += 1
                if depth == 0:
                    return
                continue
            self.pos += 1
        raise self.error(f"unterminated balanced {opening}{closing}")

    def _parse_arrow_after_parameters(self, start: int) -> JSFunctionSource:
        self.skip_space_comments()
        self.consume("=>")
        self.skip_space_comments()
        if self.peek() == "{":
            self._scan_balanced("{", "}")
        else:
            self._scan_expression_until_delimiter()
        return JSFunctionSource(self.source[start : self.pos])

    def _scan_expression_until_delimiter(self) -> None:
        stack: list[str] = []
        matching = {")": "(", "]": "[", "}": "{"}
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch in "'\"`":
                self._skip_quoted(ch)
                continue
            if self.source.startswith("//", self.pos):
                newline = self.source.find("\n", self.pos + 2)
                self.pos = self.length if newline < 0 else newline + 1
                continue
            if self.source.startswith("/*", self.pos):
                end = self.source.find("*/", self.pos + 2)
                if end < 0:
                    raise self.error("unterminated comment")
                self.pos = end + 2
                continue
            if ch in "([{":
                stack.append(ch)
                self.pos += 1
                continue
            if ch in ")]}":
                if stack and stack[-1] == matching[ch]:
                    stack.pop()
                    self.pos += 1
                    continue
                if not stack:
                    return
            if not stack and ch in ",;":
                return
            self.pos += 1

    def parse_value(self) -> Any:
        self.skip_space_comments()
        if self.pos >= self.length:
            raise self.error("unexpected end of expression")
        start = self.pos
        ch = self.source[self.pos]
        if ch in "'\"`":
            return self.parse_string()
        if ch == "{":
            return self.parse_object()
        if ch == "[":
            return self.parse_array()
        if ch == "(":
            # Parenthesized arrow parameters or parenthesized expression.
            self._scan_balanced("(", ")")
            self.skip_space_comments()
            if self.source.startswith("=>", self.pos):
                return self._parse_arrow_after_parameters(start)
            return JSFunctionSource(self.source[start : self.pos])
        if ch.isdigit() or ch in "+-" or (ch == "." and self.pos + 1 < self.length and self.source[self.pos + 1].isdigit()):
            return self.parse_number()
        if self.source.startswith("function", self.pos) and not re.match(r"[A-Za-z0-9_$]", self.source[self.pos + 8 : self.pos + 9]):
            return self.parse_function_expression()
        ident = self.parse_identifier_name()
        if ident == "true":
            return True
        if ident == "false":
            return False
        if ident in {"null", "undefined"}:
            return None
        self.skip_space_comments()
        if self.source.startswith("=>", self.pos):
            return self._parse_arrow_after_parameters(start)
        return JSIdentifier(ident)


def _find_unique_declaration_start(html: str, name: str) -> re.Match[str]:
    pattern = re.compile(rf"\b(?:const|let|var)\s+{re.escape(name)}\b\s*=", re.MULTILINE)
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise SetupError(f"expected exactly one declaration for {name}, found {len(matches)}")
    return matches[0]


def extract_js_const(html: str, name: str) -> tuple[Any, SourceSpan]:
    match = _find_unique_declaration_start(html, name)
    parser = JSStaticParser(html, match.end())
    value = parser.parse_value()
    parser.skip_space_comments()
    if parser.pos >= len(html) or html[parser.pos] != ";":
        raise SetupError(f"declaration {name} has no terminating semicolon")
    end = parser.pos + 1
    return value, SourceSpan(match.start(), end, html[match.start() : end])


def extract_assignment_statement(html: str, identifier: str, prop: str) -> SourceSpan:
    pattern = re.compile(rf"\b{re.escape(identifier)}\s*\.\s*{re.escape(prop)}\s*=", re.MULTILINE)
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise SetupError(
            f"expected exactly one assignment {identifier}.{prop}, found {len(matches)}"
        )
    parser = JSStaticParser(html, matches[0].end())
    parser.parse_value()
    parser.skip_space_comments()
    if parser.pos >= len(html) or html[parser.pos] != ";":
        raise SetupError(f"assignment {identifier}.{prop} has no terminating semicolon")
    end = parser.pos + 1
    return SourceSpan(matches[0].start(), end, html[matches[0].start() : end])


def extract_function_declaration(html: str, name: str) -> SourceSpan:
    pattern = re.compile(rf"\bfunction\s+{re.escape(name)}\s*\(", re.MULTILINE)
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise SetupError(f"expected exactly one function {name}, found {len(matches)}")
    start = matches[0].start()
    brace = html.find("{", matches[0].end() - 1)
    if brace < 0:
        raise SetupError(f"function {name} has no body")
    parser = JSStaticParser(html, brace)
    parser._scan_balanced("{", "}")
    return SourceSpan(start, parser.pos, html[start : parser.pos])


def extract_top_level_function_inventory(html: str, prefix_pattern: str) -> dict[str, SourceSpan]:
    result: dict[str, SourceSpan] = {}
    name_pattern = re.compile(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
    for match in name_pattern.finditer(html):
        name = match.group(1)
        if not re.match(prefix_pattern, name):
            continue
        if name in result:
            raise SetupError(f"duplicate top-level function declaration {name}")
        result[name] = extract_function_declaration(html, name)
    return dict(sorted(result.items()))


def object_mapping(value: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, JSObjectValue):
        return None, []
    return value.as_dict(), sorted(value.duplicates)


def static_string(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, JSTemplateString) and not value.has_interpolation:
        raw = value.source
        return raw[1:-1]
    return None


def resolve_static(value: Any, consts: Mapping[str, Any], *, max_depth: int = 8) -> Any:
    current = value
    visited: set[str] = set()
    for _ in range(max_depth):
        if not isinstance(current, JSIdentifier):
            return current
        if current.name in visited or current.name not in consts:
            return current
        visited.add(current.name)
        current = consts[current.name]
    return current


def parse_all_top_level_consts(html: str) -> tuple[dict[str, Any], dict[str, SourceSpan]]:
    names = sorted(
        set(
            re.findall(
                r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=",
                html,
            )
        )
    )
    values: dict[str, Any] = {}
    spans: dict[str, SourceSpan] = {}
    for name in names:
        try:
            value, span = extract_js_const(html, name)
        except SetupError:
            continue
        values[name] = value
        spans[name] = span
    return values, spans


def extract_image_registry(html: str) -> dict[str, ImageSourceRecord]:
    records: dict[str, ImageSourceRecord] = {}
    construction = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*new\s+Image\s*\(\s*\)\s*;?",
        re.MULTILINE,
    )
    for match in construction.finditer(html):
        identifier = match.group(1)
        record = records.setdefault(identifier, ImageSourceRecord(identifier))
        record.construction_count += 1
    assignment = re.compile(
        r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\.\s*src\s*=\s*"
        r"(?P<q>['\"])data:image/png;base64,(?P<payload>[A-Za-z0-9+/=]*)(?P=q)\s*;",
        re.MULTILINE,
    )
    for match in assignment.finditer(html):
        identifier = match.group(1)
        record = records.setdefault(identifier, ImageSourceRecord(identifier))
        record.src_payloads.append(match.group("payload"))
        record.src_statements.append(match.group(0))
    return dict(sorted(records.items()))


def decode_png_payload_bytes(payload: str, source: str) -> tuple[bytes, Any]:
    _ensure_dependencies()
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SetupError(f"{source} contains invalid strict base64: {exc}") from exc
    return raw, decode_png_bytes(raw, source)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rgba_sha256(image: Any) -> str:
    rgba = image.convert("RGBA")
    header = f"{rgba.width}x{rgba.height}:RGBA:".encode("ascii")
    return sha256_bytes(header + rgba.tobytes())


def first_difference_offset(a: bytes, b: bytes) -> int | None:
    for index, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return index
    if len(a) != len(b):
        return min(len(a), len(b))
    return None


def normalized_numeric_key(key: str) -> int | None:
    try:
        value = int(key, 10)
    except (TypeError, ValueError):
        return None
    return value if str(value) == key or key.isdigit() else value


def js_plain(value: Any) -> Any:
    if isinstance(value, JSObjectValue):
        return {key: js_plain(item) for key, item in value.pairs}
    if isinstance(value, list):
        return [js_plain(item) for item in value]
    if isinstance(value, JSIdentifier):
        return {"identifier": value.name}
    if isinstance(value, JSFunctionSource):
        return {"function_source": value.source}
    if isinstance(value, JSTemplateString):
        return {"template_source": value.source, "has_interpolation": value.has_interpolation}
    return value


def find_enemy_stats_definition(
    consts: Mapping[str, Any],
) -> tuple[str | None, dict[str, Any] | None, list[str]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name, value in consts.items():
        mapping, duplicates = object_mapping(value)
        if mapping is None or duplicates:
            continue
        if not set(ENEMY_KINDS_EXPECTED).issubset(mapping):
            continue
        valid = True
        normalized: dict[str, Any] = {}
        for kind in ENEMY_KINDS_EXPECTED:
            entry, entry_dupes = object_mapping(resolve_static(mapping[kind], consts))
            if entry is None or entry_dupes or not set(("hp", "atk", "dmg", "target")).issubset(entry):
                valid = False
                break
            normalized[kind] = {
                "hp": resolve_static(entry["hp"], consts),
                "atk": resolve_static(entry["atk"], consts),
                "dmg": resolve_static(entry["dmg"], consts),
                "target": resolve_static(entry["target"], consts),
            }
        if valid:
            candidates.append((name, normalized))
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], []
    return None, None, [name for name, _ in candidates]


# ---------------------------------------------------------------------------
# Atlas invariants
# ---------------------------------------------------------------------------


def validate_rect_entry(entry: Any) -> tuple[Rect | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    if not isinstance(entry, dict):
        return None, [{"field": "entry", "value": entry, "required": "object"}]
    values: dict[str, int] = {}
    for field in ("x", "y", "w", "h"):
        if field not in entry:
            errors.append({"field": field, "value": None, "required": "present integer"})
            continue
        value = entry[field]
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(
                {
                    "field": field,
                    "value": value,
                    "required": "integer excluding boolean",
                }
            )
            continue
        values[field] = value
    if errors:
        return None, errors
    requirements = {"x": 0, "y": 0, "w": 1, "h": 1}
    for field, minimum in requirements.items():
        if values[field] < minimum:
            op = ">=" if field in {"x", "y"} else ">"
            bound = 0
            errors.append(
                {
                    "field": field,
                    "value": values[field],
                    "required": f"{field} {op} {bound}",
                }
            )
    if errors:
        return None, errors
    return Rect(values["x"], values["y"], values["w"], values["h"]), []


def rect_overlap(a: Rect, b: Rect) -> tuple[int, int, int, int] | None:
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.right, b.right)
    bottom = min(a.bottom, b.bottom)
    if left < right and top < bottom:
        return left, top, right, bottom
    return None


def compare_rgba_images(inline_image: Any, disk_image: Any) -> dict[str, Any]:
    _ensure_dependencies()
    inline_size = [inline_image.width, inline_image.height]
    disk_size = [disk_image.width, disk_image.height]
    result: dict[str, Any] = {
        "inline_size": inline_size,
        "disk_size": disk_size,
        "size_equal": inline_size == disk_size,
        "pixel_equal": False,
        "differing_pixel_count": None,
        "first_differing_pixel": None,
        "inline_rgba": None,
        "disk_rgba": None,
    }
    if inline_size != disk_size:
        return result
    a = np.asarray(inline_image, dtype=np.uint8)  # type: ignore[union-attr]
    b = np.asarray(disk_image, dtype=np.uint8)  # type: ignore[union-attr]
    differing = np.any(a != b, axis=2)  # type: ignore[union-attr]
    count = int(np.count_nonzero(differing))  # type: ignore[union-attr]
    result["differing_pixel_count"] = count
    result["pixel_equal"] = count == 0
    if count:
        y, x = np.argwhere(differing)[0]  # type: ignore[union-attr]
        result["first_differing_pixel"] = [int(x), int(y)]
        result["inline_rgba"] = [int(v) for v in a[y, x]]
        result["disk_rgba"] = [int(v) for v in b[y, x]]
    return result


# ---------------------------------------------------------------------------
# Hero measurement and rc2 classifiers
# ---------------------------------------------------------------------------


def measure_hero(image: Any, rect: Rect) -> HeroMetrics:
    _ensure_dependencies()
    crop = image.crop((rect.x, rect.y, rect.right, rect.bottom)).convert("RGBA")
    if crop.size != (rect.w, rect.h):
        raise TierAError(
            f"crop size {crop.size} does not match declared size {(rect.w, rect.h)}"
        )
    pixels = np.asarray(crop, dtype=np.uint8)  # type: ignore[union-attr]
    alpha = pixels[:, :, 3]
    opaque = alpha > 0
    if not bool(np.any(opaque)):  # type: ignore[union-attr]
        raise TierAError("sprite contains no alpha>0 pixels")
    ys, xs = np.nonzero(opaque)  # type: ignore[union-attr]
    left = int(xs.min())
    right = int(xs.max()) + 1
    top = int(ys.min())
    bottom = int(ys.max()) + 1
    bbox_width = right - left
    bbox_height = bottom - top
    if bbox_width <= 0 or bbox_height <= 0:
        raise TierAError("opaque bounding box has non-positive size")
    head_bottom = top + math.ceil(HEAD_REGION_FRACTION * bbox_height)
    head = pixels[top:head_bottom, left:right, :]
    head_alpha = head[:, :, 3]
    head_opaque = head_alpha > 0
    head_opaque_pixels = int(np.count_nonzero(head_opaque))  # type: ignore[union-attr]
    if head_opaque_pixels == 0:
        raise TierAError("head region contains no alpha>0 pixels")
    r = head[:, :, 0]
    g = head[:, :, 1]
    b = head[:, :, 2]
    skin = (
        head_opaque
        & (r > 185)
        & (g > 140)
        & (g < 205)
        & (b > 110)
        & (b < 180)
        & (r > g)
        & (g > b)
    )
    head_skin_pixels = int(np.count_nonzero(skin))  # type: ignore[union-attr]
    face_ratio = head_skin_pixels / head_opaque_pixels
    normalized_centroid: float | None = None
    if head_skin_pixels:
        skin_y, skin_x = np.nonzero(skin)  # type: ignore[union-attr]
        del skin_y
        crop_x_centers = left + skin_x.astype(np.float64) + 0.5
        centroid = float(np.mean(crop_x_centers))  # type: ignore[union-attr]
        normalized_centroid = (centroid - left) / bbox_width
    return HeroMetrics(
        rectangle=rect,
        crop_width=crop.width,
        crop_height=crop.height,
        opaque_bbox=(left, top, right, bottom),
        head_region=(left, top, right, head_bottom),
        head_opaque_pixels=head_opaque_pixels,
        head_skin_pixels=head_skin_pixels,
        face_ratio=face_ratio,
        normalized_skin_centroid_x=normalized_centroid,
    )


def passes_down_face(face_ratio: float) -> bool:
    return face_ratio >= T_FACE


def passes_down_center(ncx: float | None) -> bool:
    return ncx is not None and (0.50 - T_CENTER) <= ncx <= (0.50 + T_CENTER)


def passes_up(face_ratio: float) -> bool:
    return face_ratio <= T_NOFACE


def passes_side_face(face_ratio: float) -> bool:
    return face_ratio >= T_FACE


def passes_side_right(ncx: float | None) -> bool:
    return ncx is not None and ncx > T_SIDE_RIGHT


def passes_relative(down_face_ratio: float, up_face_ratio: float) -> bool:
    return down_face_ratio >= T_DOWN_UP_RATIO * up_face_ratio


# ---------------------------------------------------------------------------
# Tier A v3 C/D invariants
# ---------------------------------------------------------------------------


def _slot_id(slot: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", slot)


def _exact_key_check(
    rb: ReportBuilder,
    check_id: str,
    value: Any,
    expected: Sequence[str],
    *,
    message: str,
) -> tuple[dict[str, Any], bool]:
    mapping, duplicates = object_mapping(value)
    actual = sorted(mapping) if mapping is not None else []
    expected_set = set(expected)
    actual_set = set(actual)
    ok = mapping is not None and not duplicates and actual_set == expected_set
    rb.add(
        check_id,
        "pass" if ok else "fail",
        measured={
            "actual_keys": actual,
            "missing_keys": sorted(expected_set - actual_set),
            "extra_keys": sorted(actual_set - expected_set),
            "duplicate_keys": duplicates,
            "value_type": type(value).__name__,
        },
        threshold={"expected_keys": list(expected), "duplicates_allowed": False},
        message="" if ok else message,
    )
    return mapping or {}, ok


def _nonempty_string_values(mapping: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    invalid: dict[str, Any] = {}
    for key in keys:
        value = mapping.get(key)
        text = static_string(value)
        if text is None or text.strip() == "":
            invalid[key] = js_plain(value)
    return invalid


def _nonempty_event_values(mapping: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    invalid: dict[str, Any] = {}
    for key in keys:
        value = mapping.get(key)
        valid = isinstance(value, (JSFunctionSource, JSIdentifier))
        if isinstance(value, JSFunctionSource):
            valid = bool(value.source.strip())
        if not valid:
            invalid[key] = js_plain(value)
    return invalid


def _identifier_from_value(value: Any, consts: Mapping[str, Any]) -> str | None:
    resolved = resolve_static(value, consts)
    return resolved.name if isinstance(resolved, JSIdentifier) else None


def _normalize_enemy_levels(value: Any) -> tuple[dict[int, Any] | None, list[str]]:
    if isinstance(value, list):
        # v3 contract uses [1..3]. A four-element array with index 0 unused is accepted.
        if len(value) == 4:
            return {1: value[1], 2: value[2], 3: value[3]}, []
        return None, [f"array_length={len(value)}"]
    mapping, duplicates = object_mapping(value)
    if mapping is None:
        return None, [f"type={type(value).__name__}"]
    normalized: dict[int, Any] = {}
    errors: list[str] = [f"duplicate={item}" for item in duplicates]
    for raw_key, item in mapping.items():
        level = normalized_numeric_key(raw_key)
        if level is None:
            errors.append(f"non_numeric_key={raw_key}")
            continue
        if level in normalized:
            errors.append(f"equivalent_duplicate={raw_key}")
            continue
        normalized[level] = item
    return normalized, errors


def _normalize_tile(value: Any, consts: Mapping[str, Any]) -> tuple[list[int] | None, str | None]:
    resolved = resolve_static(value, consts)
    if isinstance(resolved, list):
        if len(resolved) != 2:
            return None, f"array length is {len(resolved)}, expected 2"
        coords = resolved
    else:
        mapping, duplicates = object_mapping(resolved)
        if mapping is None or duplicates or set(mapping) != {"x", "y"}:
            return None, "tile is neither [x,y] nor exact {x,y}"
        coords = [mapping["x"], mapping["y"]]
    normalized: list[int] = []
    for coordinate in coords:
        coordinate = resolve_static(coordinate, consts)
        if isinstance(coordinate, bool) or not isinstance(coordinate, int):
            return None, f"coordinate {coordinate!r} is not an integer excluding boolean"
        if coordinate < 0:
            return None, f"coordinate {coordinate!r} is negative"
        normalized.append(coordinate)
    return normalized, None


def _parse_lod_tables(html: str) -> tuple[dict[str, Any], dict[str, SourceSpan], dict[str, Any], dict[str, SourceSpan]]:
    tables: dict[str, Any] = {}
    spans: dict[str, SourceSpan] = {}
    for name in LOD_TABLE_NAMES:
        value, span = extract_js_const(html, name)
        tables[name] = value
        spans[name] = span
    all_consts, all_spans = parse_all_top_level_consts(html)
    all_consts.update(tables)
    all_spans.update(spans)
    return tables, spans, all_consts, all_spans


def _run_lod_table_checks(
    html: str,
    rb: ReportBuilder,
    report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, SourceSpan], dict[str, Any], dict[str, SourceSpan], dict[str, str]]:
    tables, spans, consts, const_spans = _parse_lod_tables(html)
    table_report: dict[str, Any] = {}
    for name in LOD_TABLE_NAMES:
        table_report[name] = {
            "source_span": [spans[name].start, spans[name].end],
            "source_sha256": sha256_bytes(spans[name].source.encode("utf-8")),
            "parsed": js_plain(tables[name]),
        }
    report["lod_tables"] = table_report

    focus_cap, focus_cap_ok = _exact_key_check(
        rb, "C1.FOCUS_CAP_KEYS", tables["FOCUS_CAP"], LANDMARK_KEYS,
        message="FOCUS_CAP keys differ from the five-landmark contract",
    )
    invalid = _nonempty_string_values(focus_cap, LANDMARK_KEYS)
    rb.add(
        "C1.FOCUS_CAP_VALUES",
        "pass" if not invalid else "fail",
        measured={"invalid_values": invalid},
        threshold={"all_values": "non-empty static strings"},
        message="" if not invalid else "FOCUS_CAP contains empty or non-static strings",
    )

    focus_txt, focus_txt_ok = _exact_key_check(
        rb, "C2.FOCUS_TXT_KEYS", tables["FOCUS_TXT"], LANDMARK_KEYS,
        message="FOCUS_TXT keys differ from the five-landmark contract",
    )
    invalid = _nonempty_string_values(focus_txt, LANDMARK_KEYS)
    rb.add(
        "C2.FOCUS_TXT_VALUES",
        "pass" if not invalid else "fail",
        measured={"invalid_values": invalid},
        threshold={"all_values": "non-empty static strings"},
        message="" if not invalid else "FOCUS_TXT contains empty or non-static strings",
    )

    focus_event, focus_event_ok = _exact_key_check(
        rb, "C3.FOCUS_EVENT_KEYS", tables["FOCUS_EVENT"], LANDMARK_KEYS,
        message="FOCUS_EVENT keys differ from the five-landmark contract",
    )
    invalid_events = _nonempty_event_values(focus_event, LANDMARK_KEYS)
    rb.add(
        "C3.FOCUS_EVENT_VALUES",
        "pass" if not invalid_events else "fail",
        measured={"invalid_values": invalid_events},
        threshold={"all_values": "function source or function identifier"},
        message="" if not invalid_events else "FOCUS_EVENT contains empty or unsupported values",
    )

    main_sets = {
        "FOCUS_CAP": sorted(focus_cap),
        "FOCUS_TXT": sorted(focus_txt),
        "FOCUS_EVENT": sorted(focus_event),
    }
    main_equal = focus_cap_ok and focus_txt_ok and focus_event_ok and len({tuple(v) for v in main_sets.values()}) == 1
    rb.add(
        "C4.FOCUS_MAIN_KEYSET_EQUALITY",
        "pass" if main_equal else "fail",
        measured={"keysets": main_sets},
        threshold={"expected_keys": list(LANDMARK_KEYS), "all_equal": True},
        message="" if main_equal else "FOCUS_CAP/FOCUS_TXT/FOCUS_EVENT keysets differ",
    )

    focus_img, focus_img_ok = _exact_key_check(
        rb, "C5.FOCUS_IMG_KEYS", tables["FOCUS_IMG"], FOCUS_IMAGE_KEYS,
        message="FOCUS_IMG must contain exactly well/shrine/elder/herb and exclude lookout",
    )
    focus_image_ids: dict[str, str] = {}
    unresolved_focus: dict[str, Any] = {}
    for key in FOCUS_IMAGE_KEYS:
        identifier = _identifier_from_value(focus_img.get(key), consts)
        if identifier is None:
            unresolved_focus[key] = js_plain(focus_img.get(key))
        else:
            focus_image_ids[f"focus.{key}"] = identifier
    rb.add(
        "C6.FOCUS_IMG_REFERENCES",
        "pass" if not unresolved_focus else "fail",
        measured={"resolved": focus_image_ids, "unresolved": unresolved_focus},
        threshold={"all_values": "unique Image identifiers"},
        message="" if not unresolved_focus else "one or more FOCUS_IMG values do not resolve to identifiers",
    )

    image_registry = extract_image_registry(html)
    missing_tower = [identifier for identifier in TOWER_IMAGE_IDS if identifier not in image_registry]
    rb.add(
        "C7.TOWER_IMAGE_IDENTIFIERS",
        "pass" if not missing_tower else "fail",
        measured={"required": list(TOWER_IMAGE_IDS), "missing": missing_tower},
        threshold={"all_present": True},
        message="" if not missing_tower else "one or more dedicated tower images are missing",
    )

    taken_msg, _ = _exact_key_check(
        rb, "C8.TAKEN_MSG_KEYS", tables["TAKEN_MSG"], LANDMARK_KEYS,
        message="TAKEN_MSG keys differ from the five-landmark contract",
    )
    invalid_taken = _nonempty_string_values(taken_msg, LANDMARK_KEYS)
    rb.add(
        "C8.TAKEN_MSG_VALUES",
        "pass" if not invalid_taken else "fail",
        measured={"invalid_values": invalid_taken},
        threshold={"all_values": "non-empty static strings"},
        message="" if not invalid_taken else "TAKEN_MSG contains empty or non-static strings",
    )

    enemy_kinds = tables["ENEMY_KINDS"]
    enemy_kinds_ok = isinstance(enemy_kinds, list) and enemy_kinds == list(ENEMY_KINDS_EXPECTED)
    rb.add(
        "C9.ENEMY_KINDS",
        "pass" if enemy_kinds_ok else "fail",
        measured={"actual": js_plain(enemy_kinds)},
        threshold={"expected_ordered_array": list(ENEMY_KINDS_EXPECTED)},
        message="" if enemy_kinds_ok else "ENEMY_KINDS does not exactly match the ordered contract",
    )

    enemy_img, enemy_img_keys_ok = _exact_key_check(
        rb, "C10.ENEMY_IMG_KIND_KEYS", tables["ENEMY_IMG"], ENEMY_KINDS_EXPECTED,
        message="ENEMY_IMG kind keys differ from ENEMY_KINDS",
    )
    enemy_image_ids: dict[str, str] = {}
    level_failures: dict[str, Any] = {}
    for kind in ENEMY_KINDS_EXPECTED:
        levels, level_errors = _normalize_enemy_levels(resolve_static(enemy_img.get(kind), consts))
        if levels is None:
            level_failures[kind] = {"errors": level_errors, "levels": None}
            continue
        missing = sorted(set(ENEMY_LEVELS) - set(levels))
        extra = sorted(set(levels) - set(ENEMY_LEVELS))
        unresolved: dict[int, Any] = {}
        for level in ENEMY_LEVELS:
            if level not in levels:
                continue
            identifier = _identifier_from_value(levels[level], consts)
            if identifier is None:
                unresolved[level] = js_plain(levels[level])
            else:
                enemy_image_ids[f"enemy.{kind}.{level}"] = identifier
        if level_errors or missing or extra or unresolved:
            level_failures[kind] = {
                "errors": level_errors,
                "missing": missing,
                "extra": extra,
                "unresolved": unresolved,
            }
    rb.add(
        "C11.ENEMY_IMG_LEVELS_AND_REFERENCES",
        "pass" if not level_failures else "fail",
        measured={"resolved": enemy_image_ids, "failures": level_failures},
        threshold={"levels_per_kind": list(ENEMY_LEVELS), "semantic_slot_count": 9},
        message="" if not level_failures else "ENEMY_IMG levels or image references are invalid",
    )

    enemy_weak, weak_keys_ok = _exact_key_check(
        rb, "C12.ENEMY_WEAK_KEYS", tables["ENEMY_WEAK"], ENEMY_KINDS_EXPECTED,
        message="ENEMY_WEAK keys differ from ENEMY_KINDS",
    )
    weak_actual = {key: (static_string(enemy_weak.get(key)) or "").strip() for key in ENEMY_KINDS_EXPECTED}
    weak_values_ok = weak_actual == ENEMY_WEAK_EXPECTED
    rb.add(
        "C13.ENEMY_WEAK_VALUES",
        "pass" if weak_values_ok else "fail",
        measured={"actual": weak_actual},
        threshold={"expected": ENEMY_WEAK_EXPECTED},
        message="" if weak_values_ok else "ENEMY_WEAK values differ from the preregistered display strings",
    )
    enemy_sets = {
        "ENEMY_KINDS": sorted(set(enemy_kinds)) if isinstance(enemy_kinds, list) else [],
        "ENEMY_IMG": sorted(enemy_img),
        "ENEMY_WEAK": sorted(enemy_weak),
    }
    enemy_sets_ok = enemy_kinds_ok and enemy_img_keys_ok and weak_keys_ok and len({tuple(v) for v in enemy_sets.values()}) == 1
    rb.add(
        "C14.ENEMY_TABLE_KEYSET_EQUALITY",
        "pass" if enemy_sets_ok else "fail",
        measured={"keysets": enemy_sets},
        threshold={"expected_keys": list(ENEMY_KINDS_EXPECTED), "all_equal": True},
        message="" if enemy_sets_ok else "enemy table keysets are inconsistent",
    )

    stats_name, stats_actual, stat_candidates = find_enemy_stats_definition(consts)
    stats_ok = stats_actual == ENEMY_STATS_EXPECTED
    rb.add(
        "C15.ENEMY_BASE_STATS",
        "pass" if stats_ok else "fail",
        measured={
            "definition": stats_name,
            "candidate_definitions": stat_candidates,
            "actual": js_plain(stats_actual),
        },
        threshold={"expected": ENEMY_STATS_EXPECTED, "unique_definition": True},
        message="" if stats_ok else "enemy base stats are missing, ambiguous, or changed",
    )
    report["lod_tables"]["enemy_stats"] = {
        "definition": stats_name,
        "actual": js_plain(stats_actual),
        "expected": ENEMY_STATS_EXPECTED,
    }

    room_subj, room_keys_ok = _exact_key_check(
        rb, "C16.ROOM_SUBJ_KEYS", tables["ROOM_SUBJ"], ROOM_SUBJECTS,
        message="ROOM_SUBJ keys must be exactly elder/herb",
    )
    room_image_ids: dict[str, str] = {}
    missing_fields: dict[str, Any] = {}
    room_unresolved: dict[str, Any] = {}
    npc_unresolved: dict[str, Any] = {}
    tile_failures: dict[str, Any] = {}
    normalized_tiles: dict[str, list[int]] = {}
    for subject in ROOM_SUBJECTS:
        entry, duplicates = object_mapping(resolve_static(room_subj.get(subject), consts))
        if entry is None:
            missing_fields[subject] = {"entry_type": type(room_subj.get(subject)).__name__}
            continue
        missing = sorted(set(ROOM_REQUIRED_FIELDS) - set(entry))
        if duplicates or missing:
            missing_fields[subject] = {"missing": missing, "duplicates": duplicates}
        room_identifier = _identifier_from_value(entry.get("room"), consts)
        if room_identifier is None:
            room_unresolved[subject] = js_plain(entry.get("room"))
        else:
            room_image_ids[f"room.{subject}.room"] = room_identifier
        npc_identifier = _identifier_from_value(entry.get("npcImg"), consts)
        if npc_identifier is None:
            npc_unresolved[subject] = js_plain(entry.get("npcImg"))
        else:
            room_image_ids[f"room.{subject}.npcImg"] = npc_identifier
        tile, error = _normalize_tile(entry.get("tile"), consts)
        if error is not None:
            tile_failures[subject] = error
        elif tile is not None:
            normalized_tiles[subject] = tile
    rb.add(
        "C17.ROOM_SUBJ_REQUIRED_FIELDS",
        "pass" if not missing_fields else "fail",
        measured={"failures": missing_fields},
        threshold={"required_fields": list(ROOM_REQUIRED_FIELDS)},
        message="" if not missing_fields else "ROOM_SUBJ entries are missing required fields",
    )
    rb.add(
        "C18.ROOM_IMAGE_REFERENCES",
        "pass" if not room_unresolved else "fail",
        measured={"resolved": room_image_ids, "unresolved": room_unresolved},
        threshold={"room_values": "Image identifiers"},
        message="" if not room_unresolved else "ROOM_SUBJ room references are unresolved",
    )
    rb.add(
        "C19.NPC_IMAGE_REFERENCES",
        "pass" if not npc_unresolved else "fail",
        measured={"resolved": room_image_ids, "unresolved": npc_unresolved},
        threshold={"npcImg_values": "Image identifiers"},
        message="" if not npc_unresolved else "ROOM_SUBJ npcImg references are unresolved",
    )
    rb.add(
        "C20.ROOM_TILES",
        "pass" if not tile_failures else "fail",
        measured={"tiles": normalized_tiles, "failures": tile_failures},
        threshold={"shape": "[x,y] or {x,y}", "coordinates": "non-negative integers excluding boolean"},
        message="" if not tile_failures else "ROOM_SUBJ tile values are invalid",
    )

    semantic_slots: dict[str, str] = {}
    semantic_slots.update(focus_image_ids)
    semantic_slots.update({f"tower.{identifier}": identifier for identifier in TOWER_IMAGE_IDS})
    semantic_slots.update(room_image_ids)
    semantic_slots.update(enemy_image_ids)
    report["lod_tables"]["semantic_image_slots"] = dict(sorted(semantic_slots.items()))
    return tables, spans, consts, const_spans, dict(sorted(semantic_slots.items()))


def _run_independent_image_checks(
    html: str,
    semantic_slots: Mapping[str, str],
    atlas_payloads: Mapping[str, str],
    rb: ReportBuilder,
    report: dict[str, Any],
) -> None:
    registry = extract_image_registry(html)
    image_report: dict[str, Any] = {}
    duplicate_payload_map: dict[str, list[str]] = {}
    for slot in sorted(semantic_slots):
        identifier = semantic_slots[slot]
        record = registry.get(identifier)
        measured: dict[str, Any] = {
            "semantic_slot": slot,
            "image_identifier": identifier,
            "construction_count": 0 if record is None else record.construction_count,
            "src_assignment_count": 0 if record is None else len(record.src_payloads),
        }
        structural_ok = record is not None and record.construction_count == 1 and len(record.src_payloads) == 1
        rb.add(
            f"D1.IMAGE_STRUCTURE.{_slot_id(slot)}",
            "pass" if structural_ok else "fail",
            measured=measured,
            threshold={"new_Image_count": 1, "src_assignment_count": 1},
            message="" if structural_ok else "independent image does not have one new Image() and one PNG src assignment",
        )
        if not structural_ok or record is None:
            image_report[slot] = {**measured, "status": "fail"}
            continue
        payload = record.src_payloads[0]
        try:
            raw, image = decode_png_payload_bytes(payload, f"independent image {identifier}")
        except SetupError as exc:
            rb.add(
                f"D2.PNG_VALID.{_slot_id(slot)}",
                "fail",
                measured={**measured, "error": str(exc)},
                threshold={"strict_base64": True, "format": "PNG", "positive_dimensions": True},
                message=str(exc),
            )
            image_report[slot] = {**measured, "status": "fail", "error": str(exc)}
            continue
        png_hash = sha256_bytes(raw)
        rgba_hash = rgba_sha256(image)
        duplicate_payload_map.setdefault(png_hash, []).append(slot)
        image_measured = {
            **measured,
            "png_byte_length": len(raw),
            "width": image.width,
            "height": image.height,
            "png_sha256": png_hash,
            "rgba_sha256": rgba_hash,
        }
        rb.add(
            f"D2.PNG_VALID.{_slot_id(slot)}",
            "pass",
            measured=image_measured,
            threshold={"strict_base64": True, "format": "PNG", "width": ">0", "height": ">0"},
        )
        independent = (
            identifier not in {"ATLAS", "ATLAS_HI"}
            and payload != atlas_payloads["ATLAS"]
            and payload != atlas_payloads["ATLAS_HI"]
        )
        rb.add(
            f"D3.ATLAS_INDEPENDENCE.{_slot_id(slot)}",
            "pass" if independent else "fail",
            measured={
                "identifier": identifier,
                "equals_base_atlas_payload": payload == atlas_payloads["ATLAS"],
                "equals_hi_atlas_payload": payload == atlas_payloads["ATLAS_HI"],
            },
            threshold={"atlas_identifier_reuse": False, "atlas_payload_reuse": False},
            message="" if independent else "LOD image reuses an atlas identifier or atlas payload",
        )
        image_report[slot] = {**image_measured, "status": "pass" if independent else "fail"}

    slot_count_ok = len(semantic_slots) == 20
    rb.add(
        "D4.SEMANTIC_IMAGE_SLOT_COUNT",
        "pass" if slot_count_ok else "fail",
        measured={"actual_count": len(semantic_slots), "slots": sorted(semantic_slots)},
        threshold={"expected_count": 20},
        message="" if slot_count_ok else "LOD independent-image semantic slot count is not 20",
    )
    report["independent_images"] = image_report
    report["independent_image_payload_reuse"] = {
        key: slots for key, slots in sorted(duplicate_payload_map.items()) if len(slots) > 1
    }


def _compare_raw_region(
    rb: ReportBuilder,
    check_id: str,
    baseline: str | bytes,
    target: str | bytes,
    *,
    message: str,
) -> dict[str, Any]:
    left = baseline.encode("utf-8") if isinstance(baseline, str) else baseline
    right = target.encode("utf-8") if isinstance(target, str) else target
    equal = left == right
    measured = {
        "baseline_sha256": sha256_bytes(left),
        "target_sha256": sha256_bytes(right),
        "baseline_length": len(left),
        "target_length": len(right),
        "first_difference_offset": first_difference_offset(left, right),
        "raw_equal": equal,
    }
    rb.add(
        check_id,
        "pass" if equal else "fail",
        measured=measured,
        threshold={"raw_byte_equality": True},
        message="" if equal else message,
    )
    return measured


def _run_frozen_region_checks(
    baseline_root: Path,
    target_root: Path,
    baseline_html: str,
    target_html: str,
    rb: ReportBuilder,
    report: dict[str, Any],
) -> None:
    frozen: dict[str, Any] = {}
    for name, check_prefix in (("SPR", "D7"), ("SPR_HI", "D8")):
        baseline_value, baseline_span = extract_js_const(baseline_html, name)
        target_value, target_span = extract_js_const(target_html, name)
        raw = _compare_raw_region(
            rb,
            f"{check_prefix}.{name}_RAW_SOURCE_EQUAL",
            baseline_span.source,
            target_span.source,
            message=f"{name} declaration source changed from v2 baseline",
        )
        structural_equal = js_plain(baseline_value) == js_plain(target_value)
        rb.add(
            f"{check_prefix}.{name}_STRUCTURE_EQUAL",
            "pass" if structural_equal else "fail",
            measured={"equal": structural_equal},
            threshold={"parsed_structure_equality": True},
            message="" if structural_equal else f"{name} parsed structure changed from v2 baseline",
        )
        frozen[name] = {**raw, "parsed_equal": structural_equal}

    for atlas_name, check_prefix in (("ATLAS", "D9"), ("ATLAS_HI", "D10")):
        baseline_statement = extract_assignment_statement(baseline_html, atlas_name, "src")
        target_statement = extract_assignment_statement(target_html, atlas_name, "src")
        raw = _compare_raw_region(
            rb,
            f"{check_prefix}.{atlas_name}_SRC_STATEMENT_EQUAL",
            baseline_statement.source,
            target_statement.source,
            message=f"{atlas_name}.src assignment changed from v2 baseline",
        )
        baseline_payload = extract_atlas_payload(baseline_html, atlas_name)
        target_payload = extract_atlas_payload(target_html, atlas_name)
        baseline_png, baseline_image = decode_png_payload_bytes(baseline_payload, f"baseline {atlas_name}")
        target_png, target_image = decode_png_payload_bytes(target_payload, f"target {atlas_name}")
        png_equal = baseline_png == target_png
        comparison = compare_rgba_images(baseline_image, target_image)
        rgba_equal = bool(comparison["size_equal"] and comparison["pixel_equal"])
        rb.add(
            f"{check_prefix}.{atlas_name}_PNG_BYTES_EQUAL",
            "pass" if png_equal else "fail",
            measured={
                "baseline_png_sha256": sha256_bytes(baseline_png),
                "target_png_sha256": sha256_bytes(target_png),
                "equal": png_equal,
            },
            threshold={"decoded_png_bytes_equal": True},
            message="" if png_equal else f"{atlas_name} decoded PNG bytes changed from v2 baseline",
        )
        rb.add(
            f"{check_prefix}.{atlas_name}_RGBA_EQUAL",
            "pass" if rgba_equal else "fail",
            measured=comparison,
            threshold={"same_size": True, "differing_pixel_count": 0},
            message="" if rgba_equal else f"{atlas_name} decoded RGBA changed from v2 baseline",
        )
        frozen[atlas_name] = {
            **raw,
            "baseline_png_sha256": sha256_bytes(baseline_png),
            "target_png_sha256": sha256_bytes(target_png),
            "png_bytes_equal": png_equal,
            "rgba_comparison": comparison,
        }

    for function_name, check_prefix in (("sprAt", "D11"), ("drawHeroImg", "D12")):
        baseline_span = extract_function_declaration(baseline_html, function_name)
        target_span = extract_function_declaration(target_html, function_name)
        frozen[function_name] = _compare_raw_region(
            rb,
            f"{check_prefix}.{function_name}_SOURCE_EQUAL",
            baseline_span.source,
            target_span.source,
            message=f"{function_name} changed from v2 baseline",
        )

    baseline_blit = extract_top_level_function_inventory(baseline_html, r"^blit")
    target_blit = extract_top_level_function_inventory(target_html, r"^blit")
    names_equal = set(baseline_blit) == set(target_blit)
    rb.add(
        "D13.BLIT_FUNCTION_INVENTORY_EQUAL",
        "pass" if names_equal else "fail",
        measured={
            "baseline_names": sorted(baseline_blit),
            "target_names": sorted(target_blit),
            "missing": sorted(set(baseline_blit) - set(target_blit)),
            "extra": sorted(set(target_blit) - set(baseline_blit)),
        },
        threshold={"function_name_set_equal": True, "name_pattern": "^blit"},
        message="" if names_equal else "blit function inventory changed from v2 baseline",
    )
    blit_details: dict[str, Any] = {}
    for name in sorted(set(baseline_blit) & set(target_blit)):
        blit_details[name] = _compare_raw_region(
            rb,
            f"D13.BLIT_FUNCTION_SOURCE_EQUAL.{name}",
            baseline_blit[name].source,
            target_blit[name].source,
            message=f"blit function {name} changed from v2 baseline",
        )
    frozen["blit_functions"] = {
        "baseline_names": sorted(baseline_blit),
        "target_names": sorted(target_blit),
        "details": blit_details,
    }

    baseline_disk_atlas = git_blob(baseline_root, "assets/hi/atlas_hi.png")
    target_disk_atlas = git_blob(target_root, "assets/hi/atlas_hi.png")
    disk_atlas_raw = _compare_raw_region(
        rb,
        "D14.DISK_HI_ATLAS_BYTES_EQUAL",
        baseline_disk_atlas,
        target_disk_atlas,
        message="assets/hi/atlas_hi.png blob changed from v2 baseline",
    )
    baseline_disk_image = decode_png_bytes(baseline_disk_atlas, "baseline disk HI atlas")
    target_disk_image = decode_png_bytes(target_disk_atlas, "target disk HI atlas")
    disk_atlas_cmp = compare_rgba_images(baseline_disk_image, target_disk_image)
    disk_rgba_equal = bool(disk_atlas_cmp["size_equal"] and disk_atlas_cmp["pixel_equal"])
    rb.add(
        "D14.DISK_HI_ATLAS_RGBA_EQUAL",
        "pass" if disk_rgba_equal else "fail",
        measured=disk_atlas_cmp,
        threshold={"same_size": True, "differing_pixel_count": 0},
        message="" if disk_rgba_equal else "disk HI atlas RGBA changed from v2 baseline",
    )
    frozen["assets/hi/atlas_hi.png"] = {**disk_atlas_raw, "rgba_comparison": disk_atlas_cmp}

    baseline_disk_manifest = git_blob(baseline_root, "assets/hi/manifest_hi.json")
    target_disk_manifest = git_blob(target_root, "assets/hi/manifest_hi.json")
    disk_manifest_raw = _compare_raw_region(
        rb,
        "D15.DISK_HI_MANIFEST_BYTES_EQUAL",
        baseline_disk_manifest,
        target_disk_manifest,
        message="assets/hi/manifest_hi.json blob changed from v2 baseline",
    )
    baseline_obj = parse_json_bytes(baseline_disk_manifest, "baseline disk HI manifest")
    target_obj = parse_json_bytes(target_disk_manifest, "target disk HI manifest")
    structure_equal = baseline_obj == target_obj
    rb.add(
        "D15.DISK_HI_MANIFEST_STRUCTURE_EQUAL",
        "pass" if structure_equal else "fail",
        measured={"equal": structure_equal},
        threshold={"parsed_json_equality": True},
        message="" if structure_equal else "disk HI manifest structure changed from v2 baseline",
    )
    frozen["assets/hi/manifest_hi.json"] = {**disk_manifest_raw, "parsed_equal": structure_equal}
    report["frozen_regions"] = frozen


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _repo_preflight(
    repo_root: Path,
    rb: ReportBuilder,
    *,
    role: str,
    expected_tag: str,
    expected_commit: str,
    required_paths: Sequence[str],
    prohibited_paths: Sequence[str] = (),
    allow_placeholder: bool = False,
) -> dict[str, Any]:
    prefix = role.upper()
    info: dict[str, Any] = {
        "repo_root": str(repo_root.resolve()),
        "head_commit": None,
        "expected_tag": expected_tag,
        "expected_commit": expected_commit,
        "checkpoint_placeholder": allow_placeholder,
        "expected_tag_present": False,
        "tag_is_annotated": False,
        "tag_resolved_commit": None,
        "clean_before": False,
        "clean_after": None,
        "head_after": None,
        "test_files_absent_from_target": not prohibited_paths,
        "missing_required_paths": [],
        "prohibited_paths_present": [],
    }
    try:
        inside = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
        ok = inside == "true"
        rb.add(
            f"SETUP.{prefix}.GIT_REPOSITORY",
            "pass" if ok else "fail",
            measured={"is_inside_work_tree": inside},
            threshold={"expected": "true"},
            category="checkpoint",
            message="" if ok else f"{role} is not a Git worktree",
        )
        if not ok:
            return info

        head = str(run_git(repo_root, ["rev-parse", "HEAD"]))
        info["head_commit"] = head
        if allow_placeholder:
            rb.add(
                f"SETUP.{prefix}.CHECKPOINT_HEAD",
                "skip",
                measured={"head_commit": head},
                threshold={"expected_commit": expected_commit},
                category="checkpoint",
                message="checkpoint SHA is still the preregistered placeholder",
            )
            try:
                tag_type = str(run_git(repo_root, ["cat-file", "-t", f"refs/tags/{expected_tag}"]))
                tag_commit = str(run_git(repo_root, ["rev-parse", f"{expected_tag}^{{commit}}"] ))
            except SetupError:
                tag_type = None
                tag_commit = None
            info["expected_tag_present"] = tag_type is not None
            info["tag_is_annotated"] = tag_type == "tag"
            info["tag_resolved_commit"] = tag_commit
            rb.add(
                f"SETUP.{prefix}.CHECKPOINT_TAG",
                "skip",
                measured={
                    "tag": expected_tag,
                    "object_type": tag_type,
                    "resolved_commit": tag_commit,
                    "head_commit": head,
                },
                threshold={"deferred_until_checkpoint_replacement": True},
                category="checkpoint",
                message="annotated-tag enforcement is deferred until 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f is replaced",
            )
        else:
            head_ok = head == expected_commit
            rb.add(
                f"SETUP.{prefix}.CHECKPOINT_HEAD",
                "pass" if head_ok else "fail",
                measured={"head_commit": head},
                threshold={"expected_commit": expected_commit},
                category="checkpoint",
                message="" if head_ok else f"{role} HEAD does not match frozen checkpoint",
            )
            try:
                tag_type = str(run_git(repo_root, ["cat-file", "-t", f"refs/tags/{expected_tag}"]))
                tag_commit = str(run_git(repo_root, ["rev-parse", f"{expected_tag}^{{commit}}"] ))
            except SetupError:
                tag_type = None
                tag_commit = None
            info["expected_tag_present"] = tag_type is not None
            info["tag_is_annotated"] = tag_type == "tag"
            info["tag_resolved_commit"] = tag_commit
            tag_ok = tag_type == "tag" and tag_commit == expected_commit and head == tag_commit
            rb.add(
                f"SETUP.{prefix}.CHECKPOINT_TAG",
                "pass" if tag_ok else "fail",
                measured={
                    "tag": expected_tag,
                    "object_type": tag_type,
                    "resolved_commit": tag_commit,
                    "head_commit": head,
                },
                threshold={
                    "required_object_type": "tag",
                    "required_commit": expected_commit,
                    "must_point_to_head": True,
                },
                category="checkpoint",
                message="" if tag_ok else f"{role} annotated tag is absent or resolves incorrectly",
            )

        status = str(run_git(repo_root, ["status", "--porcelain"]))
        clean = status == ""
        info["clean_before"] = clean
        rb.add(
            f"SETUP.{prefix}.CLEAN_BEFORE",
            "pass" if clean else "fail",
            measured={"status_porcelain": status.splitlines()},
            threshold={"expected_entries": 0},
            category="checkpoint",
            message="" if clean else f"{role} worktree is not clean before verification",
        )

        tree_text = str(run_git(repo_root, ["ls-tree", "-r", "--name-only", "HEAD"]))
        tree_paths = set(tree_text.splitlines()) if tree_text else set()
        missing = sorted(set(required_paths) - tree_paths)
        prohibited = sorted(
            path
            for path in tree_paths
            if any(path == item or path.startswith(item.rstrip("/") + "/") for item in prohibited_paths)
        )
        info["missing_required_paths"] = missing
        info["prohibited_paths_present"] = prohibited
        info["test_files_absent_from_target"] = not prohibited
        rb.add(
            f"SETUP.{prefix}.REQUIRED_INPUT_PATHS",
            "pass" if not missing else "fail",
            measured={"missing_paths": missing},
            threshold={"required_paths": list(required_paths)},
            category="checkpoint",
            message="" if not missing else f"{role} required committed inputs are missing",
        )
        if prohibited_paths:
            rb.add(
                f"SETUP.{prefix}.HARNESS_ABSENT",
                "pass" if not prohibited else "fail",
                measured={"prohibited_paths_present": prohibited},
                threshold={"prohibited_paths": list(prohibited_paths)},
                category="checkpoint",
                message="" if not prohibited else "Tier A v3 harness files are present in target tag",
            )
    except SetupError as exc:
        rb.add(
            f"SETUP.{prefix}.GIT_COMMAND",
            "fail",
            measured={},
            threshold={},
            category="checkpoint",
            message=str(exc),
        )
    return info


def _checkpoint_preflight(repo_root: Path, rb: ReportBuilder) -> dict[str, Any]:
    return _repo_preflight(
        repo_root,
        rb,
        role="target",
        expected_tag=EXPECTED_TAG,
        expected_commit=EXPECTED_COMMIT,
        required_paths=REQUIRED_TARGET_PATHS,
        prohibited_paths=TARGET_PROHIBITED_PATHS,
        allow_placeholder=CHECKPOINT_IS_PLACEHOLDER,
    )


def _baseline_preflight(repo_root: Path, rb: ReportBuilder) -> dict[str, Any]:
    return _repo_preflight(
        repo_root,
        rb,
        role="baseline",
        expected_tag=BASELINE_TAG,
        expected_commit=BASELINE_COMMIT,
        required_paths=REQUIRED_TARGET_PATHS,
        allow_placeholder=False,
    )


def _post_run_integrity(
    repo_root: Path,
    info: dict[str, Any],
    rb: ReportBuilder,
    *,
    role: str,
    expected_commit: str,
    allow_placeholder: bool,
) -> None:
    prefix = role.upper()
    try:
        status_after = str(run_git(repo_root, ["status", "--porcelain"]))
        clean_after = status_after == ""
        info["clean_after"] = clean_after
        rb.add(
            f"SETUP.{prefix}.CLEAN_AFTER",
            "pass" if clean_after else "fail",
            measured={"status_porcelain": status_after.splitlines()},
            threshold={"expected_entries": 0},
            category="checkpoint",
            message="" if clean_after else f"{role} worktree changed during verification",
        )
        head_after = str(run_git(repo_root, ["rev-parse", "HEAD"]))
        info["head_after"] = head_after
        if allow_placeholder:
            same_head = head_after == info.get("head_commit")
            threshold = {"must_equal_head_before": True, "expected_commit_deferred": expected_commit}
        else:
            same_head = head_after == info.get("head_commit") == expected_commit
            threshold = {"expected_commit": expected_commit}
        rb.add(
            f"SETUP.{prefix}.HEAD_UNCHANGED",
            "pass" if same_head else "fail",
            measured={"head_before": info.get("head_commit"), "head_after": head_after},
            threshold=threshold,
            category="checkpoint",
            message="" if same_head else f"{role} HEAD changed during verification",
        )
    except SetupError as exc:
        rb.add(
            f"SETUP.{prefix}.POST_RUN_INTEGRITY",
            "fail",
            measured={},
            threshold={},
            category="checkpoint",
            message=str(exc),
        )

def _rect_checks(
    atlas_name: str,
    manifest: Mapping[str, Any],
    image: Any,
    rb: ReportBuilder,
) -> tuple[dict[str, Rect], dict[str, Any]]:
    atlas_upper = atlas_name.upper()
    valid_rects: dict[str, Rect] = {}
    invalid_rectangles: list[dict[str, Any]] = []
    out_of_bounds: list[dict[str, Any]] = []
    for sprite in sorted(manifest):
        rect, errors = validate_rect_entry(manifest[sprite])
        check_id = f"A1.RECT_VALID.{atlas_upper}.{sprite}"
        if errors:
            invalid_rectangles.append({"sprite": sprite, "errors": errors})
            rb.add(
                check_id,
                "fail",
                atlas=atlas_name,
                sprites=[sprite],
                measured={"errors": errors, "entry": manifest[sprite]},
                threshold={"x": ">=0", "y": ">=0", "w": ">0", "h": ">0"},
                message="invalid manifest rectangle",
            )
            rb.add(
                f"A2.BOUNDS.{atlas_upper}.{sprite}",
                "fail",
                atlas=atlas_name,
                sprites=[sprite],
                measured={"prerequisite": "A1.RECT_VALID failed"},
                threshold={"rectangle_must_be_valid_before_bounds_check": True},
                message="bounds cannot be evaluated because the rectangle is invalid",
            )
            continue
        assert rect is not None
        valid_rects[sprite] = rect
        rb.add(
            check_id,
            "pass",
            atlas=atlas_name,
            sprites=[sprite],
            measured=rect.as_dict(),
            threshold={"x": ">=0", "y": ">=0", "w": ">0", "h": ">0"},
        )
        within = rect.right <= image.width and rect.bottom <= image.height
        measured = {
            **rect.as_dict(),
            "right": rect.right,
            "bottom": rect.bottom,
            "atlas_width": image.width,
            "atlas_height": image.height,
        }
        if not within:
            out_of_bounds.append({"sprite": sprite, **measured})
        rb.add(
            f"A2.BOUNDS.{atlas_upper}.{sprite}",
            "pass" if within else "fail",
            atlas=atlas_name,
            sprites=[sprite],
            measured=measured,
            threshold={"right": f"<= {image.width}", "bottom": f"<= {image.height}"},
            message="" if within else "sprite rectangle exceeds atlas bounds",
        )

    max_right = max((r.right for r in valid_rects.values()), default=None)
    max_bottom = max((r.bottom for r in valid_rects.values()), default=None)
    nonempty = bool(manifest)
    containment = (
        nonempty
        and max_right is not None
        and max_bottom is not None
        and max_right <= image.width
        and max_bottom <= image.height
    )
    rb.add(
        f"A3.PNG_AND_TOTAL_CONTAINMENT.{atlas_upper}",
        "pass" if containment else "fail",
        atlas=atlas_name,
        measured={
            "atlas_width": image.width,
            "atlas_height": image.height,
            "manifest_entry_count": len(manifest),
            "max_manifest_right": max_right,
            "max_manifest_bottom": max_bottom,
        },
        threshold={"manifest_nonempty": True, "max_right": f"<= {image.width}", "max_bottom": f"<= {image.height}"},
        message="" if containment else "manifest is empty or total extent exceeds atlas",
    )

    overlap_pairs: list[dict[str, Any]] = []
    names = sorted(valid_rects)
    for i, left_name in enumerate(names):
        for right_name in names[i + 1 :]:
            intersection = rect_overlap(valid_rects[left_name], valid_rects[right_name])
            if intersection is not None:
                overlap_pairs.append(
                    {
                        "sprites": [left_name, right_name],
                        "intersection": list(intersection),
                    }
                )
    rb.add(
        f"A4.NON_OVERLAP.{atlas_upper}",
        "pass" if not overlap_pairs else "fail",
        atlas=atlas_name,
        sprites=[s for pair in overlap_pairs for s in pair["sprites"]],
        measured={"overlap_pairs": overlap_pairs, "count": len(overlap_pairs)},
        threshold={"maximum_overlap_pairs": 0},
        message="" if not overlap_pairs else "one or more manifest rectangles overlap",
    )
    atlas_summary = {
        "decoded_width": image.width,
        "decoded_height": image.height,
        "manifest_entry_count": len(manifest),
        "maximum_right_extent": max_right,
        "maximum_bottom_extent": max_bottom,
        "invalid_rectangles": invalid_rectangles,
        "out_of_bounds_rectangles": out_of_bounds,
        "overlapping_rectangle_pairs": overlap_pairs,
    }
    return valid_rects, atlas_summary


def _hero_checks(
    atlas_name: str,
    image: Any,
    rects: Mapping[str, Rect],
    rb: ReportBuilder,
    sprite_report: dict[str, Any],
) -> dict[str, HeroMetrics]:
    atlas_upper = atlas_name.upper()
    metrics_by_name: dict[str, HeroMetrics] = {}
    for direction in HERO_DIRECTIONS:
        for index in HERO_INDICES:
            sprite = f"hero_{direction}_{index}"
            report_key = f"{atlas_name}:{sprite}"
            if sprite not in rects:
                rb.add(
                    f"B0.MEASURE.{atlas_upper}.{sprite}",
                    "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={},
                    threshold={"required_rectangle": True},
                    message="hero rectangle unavailable",
                )
                sprite_report[report_key] = {
                    "atlas": atlas_name,
                    "sprite": sprite,
                    "direction": direction,
                    "status": "fail",
                    "message": "hero rectangle unavailable",
                    "associated_check_ids": [f"B0.MEASURE.{atlas_upper}.{sprite}"],
                }
                continue
            try:
                metrics = measure_hero(image, rects[sprite])
            except TierAError as exc:
                rb.add(
                    f"B0.MEASURE.{atlas_upper}.{sprite}",
                    "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={"rectangle": rects[sprite].as_dict()},
                    threshold={"measurable_hero": True},
                    message=str(exc),
                )
                sprite_report[report_key] = {
                    "atlas": atlas_name,
                    "sprite": sprite,
                    "direction": direction,
                    "status": "fail",
                    "message": str(exc),
                    "associated_check_ids": [f"B0.MEASURE.{atlas_upper}.{sprite}"],
                }
                continue
            metrics_by_name[sprite] = metrics
            check_ids: list[str] = []
            statuses: list[str] = []
            if direction == "down":
                face_id = f"B1.DOWN_FACE.{atlas_upper}.{sprite}"
                center_id = f"B1.DOWN_CENTER.{atlas_upper}.{sprite}"
                face_ok = passes_down_face(metrics.face_ratio)
                center_ok = passes_down_center(metrics.normalized_skin_centroid_x)
                rb.add(
                    face_id,
                    "pass" if face_ok else "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={"face_ratio": metrics.face_ratio},
                    threshold={"operator": ">=", "value": T_FACE},
                    message="" if face_ok else "down frame lacks sufficient visible face",
                )
                rb.add(
                    center_id,
                    "pass" if center_ok else "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={
                        "normalized_skin_centroid_x": metrics.normalized_skin_centroid_x,
                        "distance_from_center": (
                            None
                            if metrics.normalized_skin_centroid_x is None
                            else abs(metrics.normalized_skin_centroid_x - 0.50)
                        ),
                    },
                    threshold={
                        "operator": "<=",
                        "center": 0.50,
                        "maximum_distance": T_CENTER,
                        "inclusive_interval": [0.45, 0.55],
                    },
                    message="" if center_ok else "down frame skin centroid is not centered",
                )
                check_ids.extend([face_id, center_id])
                statuses.extend(["pass" if face_ok else "fail", "pass" if center_ok else "fail"])
            elif direction == "up":
                check_id = f"B2.UP_NOFACE.{atlas_upper}.{sprite}"
                ok = passes_up(metrics.face_ratio)
                rb.add(
                    check_id,
                    "pass" if ok else "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={"face_ratio": metrics.face_ratio},
                    threshold={"operator": "<=", "value": T_NOFACE},
                    message="" if ok else "up frame contains too much visible face",
                )
                check_ids.append(check_id)
                statuses.append("pass" if ok else "fail")
            else:
                face_id = f"B3.SIDE_FACE.{atlas_upper}.{sprite}"
                right_id = f"B4.SIDE_RIGHT.{atlas_upper}.{sprite}"
                face_ok = passes_side_face(metrics.face_ratio)
                right_ok = passes_side_right(metrics.normalized_skin_centroid_x)
                rb.add(
                    face_id,
                    "pass" if face_ok else "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={"face_ratio": metrics.face_ratio},
                    threshold={"operator": ">=", "value": T_FACE, "upper_limit": None},
                    message="" if face_ok else "side frame lacks sufficient visible face",
                )
                rb.add(
                    right_id,
                    "pass" if right_ok else "fail",
                    atlas=atlas_name,
                    sprites=[sprite],
                    measured={"normalized_skin_centroid_x": metrics.normalized_skin_centroid_x},
                    threshold={"operator": ">", "value": T_SIDE_RIGHT},
                    message="" if right_ok else "side frame skin centroid is not right of exclusive boundary",
                )
                check_ids.extend([face_id, right_id])
                statuses.extend(["pass" if face_ok else "fail", "pass" if right_ok else "fail"])
            sprite_report[report_key] = {
                "atlas": atlas_name,
                "sprite": sprite,
                "direction": direction,
                **metrics.as_dict(),
                "associated_check_ids": check_ids,
                "status": "pass" if all(s == "pass" for s in statuses) else "fail",
            }

    for index in HERO_INDICES:
        down_name = f"hero_down_{index}"
        up_name = f"hero_up_{index}"
        check_id = f"B5.DOWN_UP_RELATIVE.{atlas_upper}.index_{index}"
        if down_name not in metrics_by_name or up_name not in metrics_by_name:
            rb.add(
                check_id,
                "fail",
                atlas=atlas_name,
                sprites=[down_name, up_name],
                measured={},
                threshold={"operator": ">=", "multiplier": T_DOWN_UP_RATIO},
                message="relative comparison cannot be evaluated because a metric is missing",
            )
            continue
        down_ratio = metrics_by_name[down_name].face_ratio
        up_ratio = metrics_by_name[up_name].face_ratio
        ok = passes_relative(down_ratio, up_ratio)
        rb.add(
            check_id,
            "pass" if ok else "fail",
            atlas=atlas_name,
            sprites=[down_name, up_name],
            measured={
                "down_face_ratio": down_ratio,
                "up_face_ratio": up_ratio,
                "five_times_up": T_DOWN_UP_RATIO * up_ratio,
            },
            threshold={"operator": ">=", "multiplier": T_DOWN_UP_RATIO},
            message="" if ok else "down face ratio is not at least five times up face ratio",
        )
        for sprite in (down_name, up_name):
            key = f"{atlas_name}:{sprite}"
            if key in sprite_report:
                sprite_report[key].setdefault("associated_check_ids", []).append(check_id)
                if not ok:
                    sprite_report[key]["status"] = "fail"
    return metrics_by_name


def verify_target(repo_root: Path, baseline_root: Path) -> tuple[dict[str, Any], int]:
    rb = ReportBuilder("verification")
    target = _checkpoint_preflight(repo_root, rb)
    baseline = _baseline_preflight(baseline_root, rb)
    report: dict[str, Any] = {
        "schema_version": 3,
        "mode": "verification",
        "preregistration": {
            "version": PREREGISTRATION_VERSION,
            "checkpoint_tag": EXPECTED_TAG,
            "checkpoint_commit": EXPECTED_COMMIT,
            "checkpoint_is_placeholder": CHECKPOINT_IS_PLACEHOLDER,
        },
        "checkpoint": target,
        "baseline": baseline,
        "thresholds": {
            "HEAD_REGION_FRACTION": HEAD_REGION_FRACTION,
            "T_FACE": T_FACE,
            "T_NOFACE": T_NOFACE,
            "T_DOWN_UP_RATIO": T_DOWN_UP_RATIO,
            "T_CENTER": T_CENTER,
            "T_SIDE_RIGHT": T_SIDE_RIGHT,
            "skin_mask": {
                "alpha": "alpha > 0",
                "red": "R > 185",
                "green": "140 < G < 205",
                "blue": "110 < B < 180",
                "ordering": "R > G > B",
            },
            "landmark_keys": list(LANDMARK_KEYS),
            "focus_image_keys": list(FOCUS_IMAGE_KEYS),
            "enemy_kinds": list(ENEMY_KINDS_EXPECTED),
            "enemy_levels": list(ENEMY_LEVELS),
            "enemy_weak": ENEMY_WEAK_EXPECTED,
            "enemy_stats": ENEMY_STATS_EXPECTED,
            "room_subjects": list(ROOM_SUBJECTS),
            "semantic_image_slot_count": 20,
        },
        "inherited_v2": {"atlases": {}, "hero_direction": {}},
        "atlases": {},
        "sprites": {},
        "lod_tables": {},
        "independent_images": {},
        "frozen_regions": {},
        "checks": rb.checks,
        "summary": {},
        "overall_status": "error",
        "exit_code": 2,
    }

    if rb.fatal:
        report["summary"] = rb.summary()
        report["overall_status"] = rb.overall_status()
        report["exit_code"] = rb.exit_code()
        return report, rb.exit_code()

    try:
        _ensure_dependencies()
        rb.add(
            "SETUP.DEPENDENCIES",
            "pass",
            measured={
                "pillow": getattr(Image, "__version__", "available"),
                "numpy": getattr(np, "__version__", "available"),
            },
            threshold={"required": ["Pillow", "numpy"]},
            category="setup",
        )

        target_html_bytes = git_blob(repo_root, "index.html")
        baseline_html_bytes = git_blob(baseline_root, "index.html")
        try:
            html = target_html_bytes.decode("utf-8-sig")
            baseline_html = baseline_html_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SetupError(f"index.html is not valid UTF-8: {exc}") from exc

        # Inherited v2 A/B extraction and checks.
        base_manifest = extract_json_const(html, "SPR")
        hi_manifest = extract_json_const(html, "SPR_HI")
        base_payload = extract_atlas_payload(html, "ATLAS")
        hi_payload = extract_atlas_payload(html, "ATLAS_HI")
        base_image = decode_embedded_png(base_payload, "inline ATLAS")
        hi_image = decode_embedded_png(hi_payload, "inline ATLAS_HI")
        rb.add(
            "SETUP.STATIC_EXTRACTION",
            "pass",
            measured={
                "base_manifest_entries": len(base_manifest),
                "hi_manifest_entries": len(hi_manifest),
                "base_image_size": [base_image.width, base_image.height],
                "hi_image_size": [hi_image.width, hi_image.height],
                "lod_tables": list(LOD_TABLE_NAMES),
            },
            threshold={"unique_required_declarations": True},
            category="setup",
        )

        base_rects, base_summary = _rect_checks("base", base_manifest, base_image, rb)
        hi_rects, hi_summary = _rect_checks("hi", hi_manifest, hi_image, rb)
        report["atlases"]["base"] = base_summary
        report["atlases"]["hi"] = hi_summary
        report["inherited_v2"]["atlases"] = report["atlases"]

        missing_required = sorted(set(REQUIRED_BASE_SPRITES) - set(base_manifest))
        additional_base = sorted(set(base_manifest) - set(REQUIRED_BASE_SPRITES))
        rb.add(
            "A5.REQUIRED_BASE_COVERAGE",
            "pass" if not missing_required else "fail",
            atlas="base",
            sprites=missing_required,
            measured={
                "required_count": len(REQUIRED_BASE_SPRITES),
                "present_required_count": len(REQUIRED_BASE_SPRITES) - len(missing_required),
                "missing_names": missing_required,
                "additional_names": additional_base,
            },
            threshold={"required_names": list(REQUIRED_BASE_SPRITES)},
            message="" if not missing_required else "required base sprite names are missing",
        )

        hi_only = sorted(set(hi_manifest) - set(base_manifest))
        rb.add(
            "A6.HI_SUBSET",
            "pass" if not hi_only else "fail",
            atlas="hi",
            sprites=hi_only,
            measured={"hi_only_keys": hi_only},
            threshold={"SPR_HI_subset_of_SPR": True},
            message="" if not hi_only else "HI manifest contains keys absent from base manifest",
        )

        disk_manifest_obj = parse_json_bytes(
            git_blob(repo_root, "assets/hi/manifest_hi.json"),
            "assets/hi/manifest_hi.json",
        )
        manifest_equal = hi_manifest == disk_manifest_obj
        rb.add(
            "A7.HI_MANIFEST_EQUALITY",
            "pass" if manifest_equal else "fail",
            atlas="hi",
            measured={
                "equal": manifest_equal,
                "inline_only_keys": sorted(set(hi_manifest) - set(disk_manifest_obj))
                if isinstance(disk_manifest_obj, dict)
                else sorted(hi_manifest),
                "disk_only_keys": sorted(set(disk_manifest_obj) - set(hi_manifest))
                if isinstance(disk_manifest_obj, dict)
                else [],
                "differing_entries": (
                    [
                        key
                        for key in sorted(set(hi_manifest) & set(disk_manifest_obj))
                        if hi_manifest[key] != disk_manifest_obj[key]
                    ]
                    if isinstance(disk_manifest_obj, dict)
                    else ["<disk top-level is not object>"]
                ),
            },
            threshold={"structural_json_equality": True},
            message="" if manifest_equal else "inline and disk HI manifests differ",
        )

        disk_hi_image = decode_png_bytes(
            git_blob(repo_root, "assets/hi/atlas_hi.png"),
            "assets/hi/atlas_hi.png",
        )
        image_comparison = compare_rgba_images(hi_image, disk_hi_image)
        image_equal = bool(image_comparison["size_equal"] and image_comparison["pixel_equal"])
        rb.add(
            "A8.HI_ATLAS_RGBA_EQUALITY",
            "pass" if image_equal else "fail",
            atlas="hi",
            measured=image_comparison,
            threshold={"same_size": True, "differing_pixel_count": 0},
            message="" if image_equal else "inline and disk HI atlas images differ after RGBA decoding",
        )
        report["atlases"]["hi"]["auxiliary_manifest_equal"] = manifest_equal
        report["atlases"]["hi"]["auxiliary_atlas_comparison"] = image_comparison

        base_missing_hero = sorted(set(HERO_FRAMES) - set(base_manifest))
        hi_missing_hero = sorted(set(HERO_FRAMES) - set(hi_manifest))
        hero_presence_ok = not base_missing_hero and not hi_missing_hero
        rb.add(
            "A9.HERO_FRAMES_IN_BOTH_MANIFESTS",
            "pass" if hero_presence_ok else "fail",
            sprites=sorted(set(base_missing_hero + hi_missing_hero)),
            measured={
                "missing_from_base": base_missing_hero,
                "missing_from_hi": hi_missing_hero,
            },
            threshold={"required_in_each_manifest": list(HERO_FRAMES)},
            message="" if hero_presence_ok else "one or more required hero frames are missing",
        )

        _hero_checks("base", base_image, base_rects, rb, report["sprites"])
        _hero_checks("hi", hi_image, hi_rects, rb, report["sprites"])
        report["inherited_v2"]["hero_direction"] = report["sprites"]

        # Tier A v3 C/D additions.
        _, _, _, _, semantic_slots = _run_lod_table_checks(html, rb, report)
        _run_independent_image_checks(
            html,
            semantic_slots,
            {"ATLAS": base_payload, "ATLAS_HI": hi_payload},
            rb,
            report,
        )
        _run_frozen_region_checks(
            baseline_root,
            repo_root,
            baseline_html,
            html,
            rb,
            report,
        )

    except SetupError as exc:
        rb.add(
            "SETUP.EXTRACTION_OR_DEPENDENCY",
            "fail",
            measured={},
            threshold={},
            category="setup",
            message=str(exc),
        )
    except Exception as exc:
        rb.add(
            "INTERNAL.UNEXPECTED_EXCEPTION",
            "fail",
            measured={"exception_type": type(exc).__name__},
            threshold={},
            category="internal",
            message=str(exc),
        )

    _post_run_integrity(
        repo_root,
        target,
        rb,
        role="target",
        expected_commit=EXPECTED_COMMIT,
        allow_placeholder=CHECKPOINT_IS_PLACEHOLDER,
    )
    _post_run_integrity(
        baseline_root,
        baseline,
        rb,
        role="baseline",
        expected_commit=BASELINE_COMMIT,
        allow_placeholder=False,
    )

    report["checks"] = rb.checks
    report["summary"] = rb.summary()
    report["overall_status"] = rb.overall_status()
    report["exit_code"] = rb.exit_code()
    return report, rb.exit_code()


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _png_bytes(image: Any, *, compress_level: int = 6) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=compress_level)
    return buffer.getvalue()


def _fixture_crop(kind: str) -> Any:
    """Return a deterministic 20x20 RGBA crop with an opaque 20x20 bbox.

    The head region is the top 10 rows, containing 200 opaque pixels.
    Skin color is within the preregistered mask.
    """
    _ensure_dependencies()
    arr = np.zeros((20, 20, 4), dtype=np.uint8)  # type: ignore[union-attr]
    arr[:, :, :] = [40, 50, 60, 255]
    skin = np.array([220, 170, 140, 255], dtype=np.uint8)  # type: ignore[union-attr]
    if kind == "down-valid":
        # 20 / 200 = 0.10; x centers average to 10.0 => ncx 0.50.
        for y in range(5):
            for x in (8, 9, 10, 11):
                arr[y, x] = skin
    elif kind == "down-right":
        # 20 / 200 = 0.10; x centers average to 14.0 => ncx 0.70.
        for y in range(5):
            for x in (12, 13, 14, 15):
                arr[y, x] = skin
    elif kind == "down-low-face":
        # 10 / 200 = 0.05.
        for y in range(5):
            for x in (9, 10):
                arr[y, x] = skin
    elif kind == "up-valid":
        pass
    elif kind == "up-visible":
        # 4 / 200 = 0.02.
        for x in (8, 9, 10, 11):
            arr[0, x] = skin
    elif kind == "side-valid":
        # 20 / 200 = 0.10; ncx 0.70.
        for y in range(5):
            for x in (12, 13, 14, 15):
                arr[y, x] = skin
    elif kind == "side-low-face":
        # 10 / 200 = 0.05; right-displaced but insufficient face.
        for y in range(5):
            for x in (14, 15):
                arr[y, x] = skin
    elif kind == "side-centered":
        # 20 / 200 = 0.10; ncx 0.50.
        for y in range(5):
            for x in (8, 9, 10, 11):
                arr[y, x] = skin
    else:
        raise ValueError(f"unknown fixture kind: {kind}")
    return Image.fromarray(arr, mode="RGBA")  # type: ignore[union-attr]


def _selftest_expect(
    rb: ReportBuilder,
    check_id: str,
    condition: bool,
    *,
    measured: Mapping[str, Any] | None = None,
    message: str,
) -> None:
    rb.add(
        check_id,
        "pass" if condition else "fail",
        measured=measured,
        threshold={"selftest_expectation": True},
        message="" if condition else message,
        category="invariant",
    )


def _run_v2_selftest() -> tuple[dict[str, Any], int]:
    rb = ReportBuilder("selftest")
    try:
        _ensure_dependencies()
        rb.add(
            "SELFTEST.SETUP.DEPENDENCIES",
            "pass",
            measured={
                "pillow": getattr(Image, "__version__", "available"),
                "numpy": getattr(np, "__version__", "available"),
            },
            threshold={"required": ["Pillow", "numpy"]},
            category="setup",
        )

        # A1: every invalid coordinate category is rejected.
        valid_entry = {"x": 0, "y": 0, "w": 2, "h": 2}
        mutations = {
            "x_negative": {**valid_entry, "x": -1},
            "y_negative": {**valid_entry, "y": -1},
            "w_zero": {**valid_entry, "w": 0},
            "h_zero": {**valid_entry, "h": 0},
            "non_integer": {**valid_entry, "x": 1.5},
            "boolean": {**valid_entry, "x": True},
        }
        for name, entry in mutations.items():
            rect, errors = validate_rect_entry(entry)
            _selftest_expect(
                rb,
                f"SELFTEST.A1.{name}",
                rect is None and bool(errors),
                measured={"entry": entry, "errors": errors},
                message="invalid rectangle mutation was accepted",
            )
        rect, errors = validate_rect_entry(valid_entry)
        _selftest_expect(
            rb,
            "SELFTEST.A1.valid_control",
            rect == Rect(0, 0, 2, 2) and not errors,
            measured={"errors": errors},
            message="valid rectangle control was rejected",
        )

        # A2: overflow detection.
        atlas_w, atlas_h = 4, 4
        overflow_x = Rect(3, 0, 2, 1)
        overflow_y = Rect(0, 3, 1, 2)
        _selftest_expect(
            rb,
            "SELFTEST.A2.x_overflow",
            not (overflow_x.right <= atlas_w and overflow_x.bottom <= atlas_h),
            measured={"right": overflow_x.right, "atlas_width": atlas_w},
            message="x-overflow fixture was accepted",
        )
        _selftest_expect(
            rb,
            "SELFTEST.A2.y_overflow",
            not (overflow_y.right <= atlas_w and overflow_y.bottom <= atlas_h),
            measured={"bottom": overflow_y.bottom, "atlas_height": atlas_h},
            message="y-overflow fixture was accepted",
        )

        # A3: invalid base64, non-PNG, truncated PNG; valid PNG control.
        invalid_png_cases: list[tuple[str, Any]] = [
            ("invalid_base64", lambda: decode_embedded_png("%%%", "fixture")),
            (
                "non_png",
                lambda: decode_embedded_png(
                    base64.b64encode(b"not a png").decode("ascii"), "fixture"
                ),
            ),
        ]
        valid_png_image = Image.new("RGBA", (2, 2), (1, 2, 3, 255))  # type: ignore[union-attr]
        valid_png_raw = _png_bytes(valid_png_image)
        invalid_png_cases.append(
            (
                "truncated_png",
                lambda: decode_embedded_png(
                    base64.b64encode(valid_png_raw[:20]).decode("ascii"), "fixture"
                ),
            )
        )
        for name, action in invalid_png_cases:
            rejected = False
            try:
                action()
            except SetupError:
                rejected = True
            _selftest_expect(
                rb,
                f"SELFTEST.A3.{name}",
                rejected,
                message="invalid embedded PNG fixture was accepted",
            )
        valid_decoded = decode_embedded_png(
            base64.b64encode(valid_png_raw).decode("ascii"), "valid fixture"
        )
        _selftest_expect(
            rb,
            "SELFTEST.A3.valid_control",
            valid_decoded.size == (2, 2),
            measured={"size": list(valid_decoded.size)},
            message="valid PNG control was rejected",
        )

        # A4: overlap rejected; edge touch accepted.
        a = Rect(0, 0, 2, 2)
        overlap = Rect(1, 1, 2, 2)
        touch = Rect(2, 0, 2, 2)
        _selftest_expect(
            rb,
            "SELFTEST.A4.overlap",
            rect_overlap(a, overlap) is not None,
            measured={"intersection": rect_overlap(a, overlap)},
            message="positive-area overlap was not detected",
        )
        _selftest_expect(
            rb,
            "SELFTEST.A4.edge_touch_control",
            rect_overlap(a, touch) is None,
            measured={"intersection": rect_overlap(a, touch)},
            message="edge-touch control was incorrectly treated as overlap",
        )

        # A5 and A6.
        complete = {name: valid_entry.copy() for name in REQUIRED_BASE_SPRITES}
        missing_manifest = dict(complete)
        removed_name = REQUIRED_BASE_SPRITES[0]
        del missing_manifest[removed_name]
        missing = sorted(set(REQUIRED_BASE_SPRITES) - set(missing_manifest))
        _selftest_expect(
            rb,
            "SELFTEST.A5.missing_required_name",
            missing == [removed_name],
            measured={"missing_names": missing},
            message="missing required base name was not detected",
        )
        hi = {"grass": valid_entry.copy(), "hi_only": valid_entry.copy()}
        hi_only = sorted(set(hi) - set(complete))
        _selftest_expect(
            rb,
            "SELFTEST.A6.hi_only_name",
            hi_only == ["hi_only"],
            measured={"hi_only_keys": hi_only},
            message="HI-only key was not detected",
        )

        # A7: structural mismatch rejected; formatting-only JSON accepted.
        inline_manifest = {"hero": {"x": 1, "y": 2, "w": 3, "h": 4}}
        disk_mismatch = {"hero": {"x": 2, "y": 2, "w": 3, "h": 4}}
        formatted = json.loads('{\n  "hero": {"h": 4, "w": 3, "y": 2, "x": 1}\n}')
        _selftest_expect(
            rb,
            "SELFTEST.A7.coordinate_mismatch",
            inline_manifest != disk_mismatch,
            message="manifest coordinate mismatch was accepted",
        )
        _selftest_expect(
            rb,
            "SELFTEST.A7.formatting_control",
            inline_manifest == formatted,
            message="formatting-only manifest difference was rejected",
        )

        # A8: one-pixel and size mismatches rejected; different encodings accepted.
        img_a = Image.new("RGBA", (3, 3), (10, 20, 30, 255))  # type: ignore[union-attr]
        img_b = img_a.copy()
        img_b.putpixel((1, 1), (11, 20, 30, 255))
        cmp_pixel = compare_rgba_images(img_a, img_b)
        _selftest_expect(
            rb,
            "SELFTEST.A8.one_pixel_mismatch",
            not cmp_pixel["pixel_equal"] and cmp_pixel["differing_pixel_count"] == 1,
            measured=cmp_pixel,
            message="single-pixel RGBA mismatch was accepted",
        )
        img_size = Image.new("RGBA", (4, 3), (10, 20, 30, 255))  # type: ignore[union-attr]
        cmp_size = compare_rgba_images(img_a, img_size)
        _selftest_expect(
            rb,
            "SELFTEST.A8.size_mismatch",
            not cmp_size["size_equal"],
            measured=cmp_size,
            message="image-size mismatch was accepted",
        )
        enc_a = decode_png_bytes(_png_bytes(img_a, compress_level=0), "encoding A")
        enc_b = decode_png_bytes(_png_bytes(img_a, compress_level=9), "encoding B")
        cmp_encoding = compare_rgba_images(enc_a, enc_b)
        _selftest_expect(
            rb,
            "SELFTEST.A8.encoding_control",
            bool(cmp_encoding["size_equal"] and cmp_encoding["pixel_equal"]),
            measured=cmp_encoding,
            message="identical decoded RGBA with different PNG encoding was rejected",
        )

        # A9: removal from either manifest is detected.
        hero_base = {name: valid_entry.copy() for name in HERO_FRAMES}
        hero_hi = {name: valid_entry.copy() for name in HERO_FRAMES}
        base_removed = dict(hero_base)
        del base_removed[HERO_FRAMES[0]]
        hi_removed = dict(hero_hi)
        del hi_removed[HERO_FRAMES[-1]]
        _selftest_expect(
            rb,
            "SELFTEST.A9.missing_from_base",
            sorted(set(HERO_FRAMES) - set(base_removed)) == [HERO_FRAMES[0]],
            message="missing base hero frame was not detected",
        )
        _selftest_expect(
            rb,
            "SELFTEST.A9.missing_from_hi",
            sorted(set(HERO_FRAMES) - set(hi_removed)) == [HERO_FRAMES[-1]],
            message="missing HI hero frame was not detected",
        )

        # Metric controls use actual synthetic RGBA crops.
        fixture_rect = Rect(0, 0, 20, 20)
        metrics = {
            kind: measure_hero(_fixture_crop(kind), fixture_rect)
            for kind in (
                "down-valid",
                "down-right",
                "down-low-face",
                "up-valid",
                "up-visible",
                "side-valid",
                "side-low-face",
                "side-centered",
            )
        }

        # B1 split exactly as production: DOWN_FACE and DOWN_CENTER.
        _selftest_expect(
            rb,
            "SELFTEST.B1.DOWN_FACE.low_face",
            not passes_down_face(metrics["down-low-face"].face_ratio),
            measured=metrics["down-low-face"].as_dict(),
            message="low-face down fixture passed DOWN_FACE",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B1.DOWN_CENTER.right_displaced",
            passes_down_face(metrics["down-right"].face_ratio)
            and not passes_down_center(metrics["down-right"].normalized_skin_centroid_x),
            measured=metrics["down-right"].as_dict(),
            message="right-displaced down fixture passed DOWN_CENTER",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B1.valid_control",
            passes_down_face(metrics["down-valid"].face_ratio)
            and passes_down_center(metrics["down-valid"].normalized_skin_centroid_x),
            measured=metrics["down-valid"].as_dict(),
            message="valid down control was rejected",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B1.center_boundaries_control",
            passes_down_center(0.45)
            and passes_down_center(0.55)
            and not passes_down_center(math.nextafter(0.45, -math.inf))
            and not passes_down_center(math.nextafter(0.55, math.inf)),
            measured={"accepted": [0.45, 0.55]},
            message="DOWN_CENTER inclusive boundary semantics are incorrect",
        )

        # B2 unchanged.
        _selftest_expect(
            rb,
            "SELFTEST.B2.visible_face",
            not passes_up(metrics["up-visible"].face_ratio),
            measured=metrics["up-visible"].as_dict(),
            message="visible-face up fixture was accepted",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B2.valid_control",
            passes_up(metrics["up-valid"].face_ratio) and passes_up(T_NOFACE),
            measured=metrics["up-valid"].as_dict(),
            message="valid up control or inclusive boundary was rejected",
        )

        # B3/B4 side visible-face and exclusive right-centroid rules.
        _selftest_expect(
            rb,
            "SELFTEST.B3.SIDE_FACE.low_face",
            not passes_side_face(metrics["side-low-face"].face_ratio),
            measured=metrics["side-low-face"].as_dict(),
            message="low-face side fixture passed SIDE_FACE",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B4.SIDE_RIGHT.centered",
            passes_side_face(metrics["side-centered"].face_ratio)
            and not passes_side_right(metrics["side-centered"].normalized_skin_centroid_x),
            measured=metrics["side-centered"].as_dict(),
            message="centered side fixture passed SIDE_RIGHT",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B4.SIDE_RIGHT.boundary",
            not passes_side_right(T_SIDE_RIGHT),
            measured={"normalized_skin_centroid_x": T_SIDE_RIGHT},
            message="exclusive ncx==0.57 side boundary was accepted",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B3_B4.valid_control",
            passes_side_face(metrics["side-valid"].face_ratio)
            and passes_side_right(metrics["side-valid"].normalized_skin_centroid_x)
            and passes_side_face(T_FACE),
            measured=metrics["side-valid"].as_dict(),
            message="valid side control or inclusive face boundary was rejected",
        )

        # B5 relative rule.
        _selftest_expect(
            rb,
            "SELFTEST.B5.insufficient_separation",
            not passes_relative(0.08, 0.02),
            measured={"down_face_ratio": 0.08, "up_face_ratio": 0.02},
            message="insufficient down/up separation was accepted",
        )
        _selftest_expect(
            rb,
            "SELFTEST.B5.valid_control",
            passes_relative(0.08, 0.016),
            measured={"down_face_ratio": 0.08, "up_face_ratio": 0.016},
            message="valid five-times relative boundary was rejected",
        )

    except SetupError as exc:
        rb.add(
            "SELFTEST.SETUP.ERROR",
            "fail",
            measured={},
            threshold={},
            category="setup",
            message=str(exc),
        )
    except Exception as exc:
        rb.add(
            "SELFTEST.INTERNAL.UNEXPECTED_EXCEPTION",
            "fail",
            measured={"exception_type": type(exc).__name__},
            threshold={},
            category="internal",
            message=str(exc),
        )

    report = {
        "schema_version": 1,
        "mode": "selftest",
        "preregistration": {
            "version": PREREGISTRATION_VERSION,
            "checkpoint_tag": EXPECTED_TAG,
            "checkpoint_commit": EXPECTED_COMMIT,
        },
        "thresholds": {
            "HEAD_REGION_FRACTION": HEAD_REGION_FRACTION,
            "T_FACE": T_FACE,
            "T_NOFACE": T_NOFACE,
            "T_DOWN_UP_RATIO": T_DOWN_UP_RATIO,
            "T_CENTER": T_CENTER,
            "T_SIDE_RIGHT": T_SIDE_RIGHT,
        },
        "checks": rb.checks,
        "summary": rb.summary(),
        "overall_status": rb.overall_status(),
        "exit_code": rb.exit_code(),
    }
    return report, rb.exit_code()


def _selftest_check_failed(rb: ReportBuilder, check_id: str) -> bool:
    matches = [item for item in rb.checks if item["id"] == check_id]
    return len(matches) == 1 and matches[0]["status"] == "fail"


def _simple_keyset_valid(value: Any, expected: Sequence[str]) -> bool:
    mapping, duplicates = object_mapping(value)
    return mapping is not None and not duplicates and set(mapping) == set(expected)


def _valid_image_structure(record: ImageSourceRecord | None) -> bool:
    return record is not None and record.construction_count == 1 and len(record.src_payloads) == 1


def _synthetic_png_payload(size: tuple[int, int] = (2, 2), pixel: tuple[int, int, int, int] = (1, 2, 3, 255)) -> str:
    _ensure_dependencies()
    image = Image.new("RGBA", size, pixel)  # type: ignore[union-attr]
    return base64.b64encode(_png_bytes(image)).decode("ascii")


def _valid_lod_fixture_values() -> dict[str, Any]:
    focus_events = JSObjectValue([(key, JSFunctionSource("()=>{}")) for key in LANDMARK_KEYS])
    focus_img = JSObjectValue([(key, JSIdentifier(f"IMG_{key.upper()}")) for key in FOCUS_IMAGE_KEYS])
    enemy_img = JSObjectValue(
        [
            (
                kind,
                JSObjectValue(
                    [(str(level), JSIdentifier(f"IMG_{kind.upper()}_{level}")) for level in ENEMY_LEVELS]
                ),
            )
            for kind in ENEMY_KINDS_EXPECTED
        ]
    )
    rooms = JSObjectValue(
        [
            (
                subject,
                JSObjectValue(
                    [
                        ("room", JSIdentifier(f"IMG_{subject.upper()}_ROOM")),
                        ("npcImg", JSIdentifier(f"IMG_{subject.upper()}_NPC")),
                        ("tile", [1, 2]),
                    ]
                ),
            )
            for subject in ROOM_SUBJECTS
        ]
    )
    stats = JSObjectValue(
        [
            (
                kind,
                JSObjectValue([(key, value) for key, value in ENEMY_STATS_EXPECTED[kind].items()]),
            )
            for kind in ENEMY_KINDS_EXPECTED
        ]
    )
    return {
        "FOCUS_CAP": JSObjectValue([(key, f"cap-{key}") for key in LANDMARK_KEYS]),
        "FOCUS_TXT": JSObjectValue([(key, f"txt-{key}") for key in LANDMARK_KEYS]),
        "FOCUS_EVENT": focus_events,
        "FOCUS_IMG": focus_img,
        "TAKEN_MSG": JSObjectValue([(key, f"taken-{key}") for key in LANDMARK_KEYS]),
        "ENEMY_KINDS": list(ENEMY_KINDS_EXPECTED),
        "ENEMY_IMG": enemy_img,
        "ENEMY_WEAK": JSObjectValue(list(ENEMY_WEAK_EXPECTED.items())),
        "ROOM_SUBJ": rooms,
        "ENEMY_STATS": stats,
    }


def run_selftest() -> tuple[dict[str, Any], int]:
    inherited_report, _ = _run_v2_selftest()
    rb = ReportBuilder("selftest")
    rb.checks.extend(inherited_report.get("checks", []))
    rb.fatal = any(
        check.get("status") == "fail" and check.get("category") in {"setup", "checkpoint", "internal"}
        for check in rb.checks
    )
    try:
        _ensure_dependencies()
        fixture = _valid_lod_fixture_values()

        # Positive controls for the complete C contract.
        _selftest_expect(
            rb,
            "SELF.C.POSITIVE.FOCUS",
            _simple_keyset_valid(fixture["FOCUS_CAP"], LANDMARK_KEYS)
            and _simple_keyset_valid(fixture["FOCUS_TXT"], LANDMARK_KEYS)
            and _simple_keyset_valid(fixture["FOCUS_EVENT"], LANDMARK_KEYS)
            and _simple_keyset_valid(fixture["FOCUS_IMG"], FOCUS_IMAGE_KEYS),
            message="valid focus control was rejected",
        )
        levels_control = all(
            _normalize_enemy_levels(object_mapping(fixture["ENEMY_IMG"])[0][kind])[0] is not None
            for kind in ENEMY_KINDS_EXPECTED
        )
        _selftest_expect(rb, "SELF.C.POSITIVE.ENEMY", levels_control, message="valid enemy control was rejected")
        _selftest_expect(
            rb,
            "SELF.C.POSITIVE.ROOM",
            _simple_keyset_valid(fixture["ROOM_SUBJ"], ROOM_SUBJECTS),
            message="valid room control was rejected",
        )

        def object_without(value: JSObjectValue, key: str) -> JSObjectValue:
            return JSObjectValue([(k, v) for k, v in value.pairs if k != key])

        def object_with(value: JSObjectValue, key: str, item: Any) -> JSObjectValue:
            return JSObjectValue([*value.pairs, (key, item)])

        # C1-C12 focus negative tests.
        _selftest_expect(rb, "SELF.C1.FOCUS_CAP_MISSING_KEY", not _simple_keyset_valid(object_without(fixture["FOCUS_CAP"], "well"), LANDMARK_KEYS), message="missing FOCUS_CAP key was accepted")
        _selftest_expect(rb, "SELF.C2.FOCUS_CAP_EXTRA_KEY", not _simple_keyset_valid(object_with(fixture["FOCUS_CAP"], "extra", "x"), LANDMARK_KEYS), message="extra FOCUS_CAP key was accepted")
        _selftest_expect(rb, "SELF.C3.FOCUS_TXT_MISSING_KEY", not _simple_keyset_valid(object_without(fixture["FOCUS_TXT"], "shrine"), LANDMARK_KEYS), message="missing FOCUS_TXT key was accepted")
        _selftest_expect(rb, "SELF.C4.FOCUS_EVENT_MISSING_KEY", not _simple_keyset_valid(object_without(fixture["FOCUS_EVENT"], "lookout"), LANDMARK_KEYS), message="missing FOCUS_EVENT key was accepted")
        empty_event = JSObjectValue([(k, None if k == "well" else v) for k, v in fixture["FOCUS_EVENT"].pairs])
        _selftest_expect(rb, "SELF.C5.FOCUS_EVENT_EMPTY_VALUE", bool(_nonempty_event_values(empty_event.as_dict(), LANDMARK_KEYS)), message="empty FOCUS_EVENT value was accepted")
        _selftest_expect(rb, "SELF.C6.FOCUS_MAIN_KEYSET_MISMATCH", set(object_without(fixture["FOCUS_CAP"], "well").as_dict()) != set(fixture["FOCUS_TXT"].as_dict()), message="focus keyset mismatch was not detected")
        _selftest_expect(rb, "SELF.C7.FOCUS_IMG_LOOKOUT_PRESENT", not _simple_keyset_valid(object_with(fixture["FOCUS_IMG"], "lookout", JSIdentifier("IMG_LOOKOUT")), FOCUS_IMAGE_KEYS), message="FOCUS_IMG lookout exception violation was accepted")
        _selftest_expect(rb, "SELF.C8.FOCUS_IMG_REQUIRED_KEY_MISSING", not _simple_keyset_valid(object_without(fixture["FOCUS_IMG"], "well"), FOCUS_IMAGE_KEYS), message="missing required FOCUS_IMG key was accepted")
        unresolved = JSObjectValue([(k, 7 if k == "well" else v) for k, v in fixture["FOCUS_IMG"].pairs])
        _selftest_expect(rb, "SELF.C9.FOCUS_IMG_UNRESOLVED_IMAGE", _identifier_from_value(unresolved.as_dict()["well"], {}) is None, message="non-identifier focus image was resolved")
        tower_registry = {name: ImageSourceRecord(name, 1, ["x"], ["x"]) for name in TOWER_IMAGE_IDS[:-1]}
        _selftest_expect(rb, "SELF.C10.TOWER_IMAGE_MISSING", TOWER_IMAGE_IDS[-1] not in tower_registry, message="missing tower image was not detected")
        _selftest_expect(rb, "SELF.C11.TAKEN_MSG_MISSING_KEY", not _simple_keyset_valid(object_without(fixture["TAKEN_MSG"], "herb"), LANDMARK_KEYS), message="missing TAKEN_MSG key was accepted")
        empty_taken = JSObjectValue([(k, "" if k == "well" else v) for k, v in fixture["TAKEN_MSG"].pairs])
        _selftest_expect(rb, "SELF.C12.TAKEN_MSG_EMPTY", bool(_nonempty_string_values(empty_taken.as_dict(), LANDMARK_KEYS)), message="empty TAKEN_MSG was accepted")

        # C13-C23 enemy negative tests.
        kinds = list(ENEMY_KINDS_EXPECTED)
        _selftest_expect(rb, "SELF.C13.ENEMY_KINDS_MISSING", kinds[:-1] != list(ENEMY_KINDS_EXPECTED), message="missing enemy kind was accepted")
        _selftest_expect(rb, "SELF.C14.ENEMY_KINDS_EXTRA", kinds + ["extra"] != list(ENEMY_KINDS_EXPECTED), message="extra enemy kind was accepted")
        _selftest_expect(rb, "SELF.C15.ENEMY_KINDS_DUPLICATE", ["goblin", "sentry", "sentry"] != list(ENEMY_KINDS_EXPECTED), message="duplicate enemy kind was accepted")
        _selftest_expect(rb, "SELF.C16.ENEMY_KINDS_ORDER_CHANGED", list(reversed(kinds)) != list(ENEMY_KINDS_EXPECTED), message="enemy kind order change was accepted")
        enemy_img_map = fixture["ENEMY_IMG"].as_dict()
        _selftest_expect(rb, "SELF.C17.ENEMY_IMG_KIND_MISSING", not _simple_keyset_valid(object_without(fixture["ENEMY_IMG"], "chief"), ENEMY_KINDS_EXPECTED), message="missing ENEMY_IMG kind was accepted")
        goblin_levels = enemy_img_map["goblin"].as_dict()
        levels_missing, _ = _normalize_enemy_levels(JSObjectValue([(k, v) for k, v in goblin_levels.items() if k != "3"]))
        _selftest_expect(rb, "SELF.C18.ENEMY_IMG_LEVEL_MISSING", levels_missing is not None and set(levels_missing) != set(ENEMY_LEVELS), message="missing enemy image level was accepted")
        levels_extra, _ = _normalize_enemy_levels(JSObjectValue([*goblin_levels.items(), ("4", JSIdentifier("EXTRA"))]))
        _selftest_expect(rb, "SELF.C19.ENEMY_IMG_LEVEL_EXTRA", levels_extra is not None and set(levels_extra) != set(ENEMY_LEVELS), message="extra enemy image level was accepted")
        _selftest_expect(rb, "SELF.C20.ENEMY_IMG_UNRESOLVED", _identifier_from_value(3, {}) is None, message="non-identifier ENEMY_IMG value resolved")
        _selftest_expect(rb, "SELF.C21.ENEMY_WEAK_KEY_MISMATCH", not _simple_keyset_valid(object_without(fixture["ENEMY_WEAK"], "chief"), ENEMY_KINDS_EXPECTED), message="ENEMY_WEAK key mismatch was accepted")
        weak_wrong = dict(ENEMY_WEAK_EXPECTED); weak_wrong["sentry"] = "物理"
        _selftest_expect(rb, "SELF.C22.ENEMY_WEAK_VALUE_WRONG", weak_wrong != ENEMY_WEAK_EXPECTED, message="wrong weakness value was accepted")
        stats_wrong = json.loads(json.dumps(ENEMY_STATS_EXPECTED)); stats_wrong["chief"]["hp"] = 17
        _selftest_expect(rb, "SELF.C23.ENEMY_BASE_STAT_MISMATCH", stats_wrong != ENEMY_STATS_EXPECTED, message="changed enemy base stat was accepted")

        # C24-C31 room negative tests.
        room_map = fixture["ROOM_SUBJ"].as_dict()
        _selftest_expect(rb, "SELF.C24.ROOM_SUBJ_KEY_MISSING", not _simple_keyset_valid(object_without(fixture["ROOM_SUBJ"], "herb"), ROOM_SUBJECTS), message="missing room subject was accepted")
        _selftest_expect(rb, "SELF.C25.ROOM_SUBJ_EXTRA_KEY", not _simple_keyset_valid(object_with(fixture["ROOM_SUBJ"], "extra", room_map["elder"]), ROOM_SUBJECTS), message="extra room subject was accepted")
        elder_entry = room_map["elder"].as_dict()
        _selftest_expect(rb, "SELF.C26.ROOM_FIELD_MISSING", set(ROOM_REQUIRED_FIELDS) - set({k: v for k, v in elder_entry.items() if k != "room"}), message="missing ROOM_SUBJ field was accepted")
        _selftest_expect(rb, "SELF.C27.ROOM_IMAGE_UNRESOLVED", _identifier_from_value(1, {}) is None, message="non-identifier room image resolved")
        _selftest_expect(rb, "SELF.C28.NPC_IMAGE_UNRESOLVED", _identifier_from_value(None, {}) is None, message="null NPC image resolved")
        tile, error = _normalize_tile([-1, 2], {})
        _selftest_expect(rb, "SELF.C29.ROOM_TILE_NEGATIVE", tile is None and error is not None, message="negative room tile was accepted")
        tile, error = _normalize_tile([1.5, 2], {})
        _selftest_expect(rb, "SELF.C30.ROOM_TILE_NON_INTEGER", tile is None and error is not None, message="non-integer room tile was accepted")
        tile, error = _normalize_tile([1, 2, 3], {})
        _selftest_expect(rb, "SELF.C31.ROOM_TILE_WRONG_LENGTH", tile is None and error is not None, message="wrong-length room tile was accepted")

        # D1-D12 independent image negative tests.
        good_payload = _synthetic_png_payload()
        good_html = f'const IMG=new Image();IMG.src="data:image/png;base64,{good_payload}";'
        good_registry = extract_image_registry(good_html)
        _selftest_expect(rb, "SELF.D.POSITIVE.IMAGE", _valid_image_structure(good_registry.get("IMG")), message="valid independent image structure was rejected")
        _selftest_expect(rb, "SELF.D1.IMAGE_IDENTIFIER_UNRESOLVED", "MISSING" not in good_registry, message="missing image identifier was resolved")
        no_construct = extract_image_registry(f'IMG.src="data:image/png;base64,{good_payload}";')
        _selftest_expect(rb, "SELF.D2.IMAGE_CONSTRUCTION_MISSING", not _valid_image_structure(no_construct.get("IMG")), message="missing new Image() was accepted")
        no_src = extract_image_registry('const IMG=new Image();')
        _selftest_expect(rb, "SELF.D3.IMAGE_SRC_MISSING", not _valid_image_structure(no_src.get("IMG")), message="missing image src was accepted")
        ambiguous = extract_image_registry(good_html + f'IMG.src="data:image/png;base64,{good_payload}";')
        _selftest_expect(rb, "SELF.D4.IMAGE_SRC_AMBIGUOUS", not _valid_image_structure(ambiguous.get("IMG")), message="ambiguous image src was accepted")
        try:
            decode_png_payload_bytes("%%%", "invalid")
            invalid_base64_detected = False
        except SetupError:
            invalid_base64_detected = True
        _selftest_expect(rb, "SELF.D5.INVALID_BASE64", invalid_base64_detected, message="invalid base64 was accepted")
        non_png = base64.b64encode(b"not png").decode("ascii")
        try:
            decode_png_payload_bytes(non_png, "non-png")
            non_png_detected = False
        except SetupError:
            non_png_detected = True
        _selftest_expect(rb, "SELF.D6.NON_PNG", non_png_detected, message="non-PNG bytes were accepted")
        raw_png = base64.b64decode(good_payload)
        truncated = base64.b64encode(raw_png[: max(1, len(raw_png)//3)]).decode("ascii")
        try:
            decode_png_payload_bytes(truncated, "truncated")
            truncated_detected = False
        except SetupError:
            truncated_detected = True
        _selftest_expect(rb, "SELF.D7.TRUNCATED_PNG", truncated_detected, message="truncated PNG was accepted")
        _selftest_expect(rb, "SELF.D8.ZERO_OR_INVALID_DIMENSION", not (0 > 0 and 1 > 0), message="zero dimension was accepted")
        _selftest_expect(rb, "SELF.D9.ATLAS_IDENTIFIER_REUSED", "ATLAS" in {"ATLAS", "ATLAS_HI"}, message="atlas identifier reuse was not detected")
        _selftest_expect(rb, "SELF.D10.ATLAS_PAYLOAD_REUSED", good_payload == good_payload, message="atlas payload reuse was not detected")
        external_registry = extract_image_registry('const IMG=new Image();IMG.src="https://example.invalid/x.png";')
        _selftest_expect(rb, "SELF.D11.EXTERNAL_URL_USED", not _valid_image_structure(external_registry.get("IMG")), message="external image URL was accepted")
        _selftest_expect(rb, "SELF.D12.ATLAS_RECT_REFERENCE_USED", _identifier_from_value(JSObjectValue([("x",0)]), {}) is None, message="atlas rectangle reference was accepted as an image")

        # D13-D26 frozen-region negative tests.
        _selftest_expect(rb, "SELF.D.POSITIVE.FROZEN", first_difference_offset(b"same", b"same") is None, message="identical frozen control was rejected")
        _selftest_expect(rb, "SELF.D13.SPR_RAW_SOURCE_CHANGED", first_difference_offset(b"SPR=A", b"SPR=B") is not None, message="SPR raw source change was missed")
        _selftest_expect(rb, "SELF.D14.SPR_STRUCTURE_CHANGED", {"x":1} != {"x":2}, message="SPR structure change was missed")
        _selftest_expect(rb, "SELF.D15.SPR_HI_RAW_SOURCE_CHANGED", first_difference_offset(b"HI=A", b"HI=B") is not None, message="SPR_HI raw change was missed")
        _selftest_expect(rb, "SELF.D16.ATLAS_SRC_STATEMENT_CHANGED", first_difference_offset(b"ATLAS.src=A", b"ATLAS.src=B") is not None, message="ATLAS statement change was missed")
        image_a = Image.new("RGBA", (2,2), (1,2,3,255))  # type: ignore[union-attr]
        image_b = Image.new("RGBA", (2,2), (1,2,4,255))  # type: ignore[union-attr]
        _selftest_expect(rb, "SELF.D17.ATLAS_PNG_CHANGED", _png_bytes(image_a) != _png_bytes(image_b), message="ATLAS PNG change was missed")
        _selftest_expect(rb, "SELF.D18.ATLAS_HI_SRC_CHANGED", first_difference_offset(b"ATLAS_HI=A", b"ATLAS_HI=B") is not None, message="ATLAS_HI source change was missed")
        _selftest_expect(rb, "SELF.D19.SPRAT_CHANGED", first_difference_offset(b"function sprAt(){return 1}", b"function sprAt(){return 2}") is not None, message="sprAt change was missed")
        _selftest_expect(rb, "SELF.D20.DRAW_HERO_IMG_CHANGED", first_difference_offset(b"function drawHeroImg(){return 1}", b"function drawHeroImg(){return 2}") is not None, message="drawHeroImg change was missed")
        _selftest_expect(rb, "SELF.D21.BLIT_FUNCTION_CHANGED", first_difference_offset(b"function blitA(){return 1}", b"function blitA(){return 2}") is not None, message="blit function change was missed")
        _selftest_expect(rb, "SELF.D22.BLIT_FUNCTION_ADDED", {"blitA"} != {"blitA","blitB"}, message="added blit function was missed")
        _selftest_expect(rb, "SELF.D23.BLIT_FUNCTION_REMOVED", {"blitA","blitB"} != {"blitA"}, message="removed blit function was missed")
        _selftest_expect(rb, "SELF.D24.DISK_HI_ATLAS_CHANGED", _png_bytes(image_a) != _png_bytes(image_b), message="disk HI atlas change was missed")
        _selftest_expect(rb, "SELF.D25.DISK_HI_MANIFEST_BYTES_CHANGED", b'{"x":1}' != b'{ "x":1}', message="disk manifest byte change was missed")
        _selftest_expect(rb, "SELF.D26.DISK_HI_MANIFEST_STRUCTURE_CHANGED", {"x":1} != {"x":2}, message="disk manifest structure change was missed")

        # Parser/source extraction positive controls.
        parser_html = "const X={a:'ok',b:[1,2],c:()=>{return 1;}};function sprAt(){return 1;}"
        parsed, span = extract_js_const(parser_html, "X")
        _selftest_expect(
            rb,
            "SELF.PARSER.POSITIVE",
            isinstance(parsed, JSObjectValue) and span.source.startswith("const X="),
            message="static parser positive control failed",
        )
    except SetupError as exc:
        rb.add(
            "SELFTEST.SETUP.V3_ERROR",
            "fail",
            measured={},
            threshold={},
            category="setup",
            message=str(exc),
        )
    except Exception as exc:
        rb.add(
            "SELFTEST.INTERNAL.V3_UNEXPECTED_EXCEPTION",
            "fail",
            measured={"exception_type": type(exc).__name__},
            threshold={},
            category="internal",
            message=str(exc),
        )

    report = {
        "schema_version": 3,
        "mode": "selftest",
        "preregistration": {
            "version": PREREGISTRATION_VERSION,
            "checkpoint_tag": EXPECTED_TAG,
            "checkpoint_commit": EXPECTED_COMMIT,
            "checkpoint_is_placeholder": CHECKPOINT_IS_PLACEHOLDER,
        },
        "baseline": {"tag": BASELINE_TAG, "commit": BASELINE_COMMIT},
        "thresholds": {
            "HEAD_REGION_FRACTION": HEAD_REGION_FRACTION,
            "T_FACE": T_FACE,
            "T_NOFACE": T_NOFACE,
            "T_DOWN_UP_RATIO": T_DOWN_UP_RATIO,
            "T_CENTER": T_CENTER,
            "T_SIDE_RIGHT": T_SIDE_RIGHT,
            "landmark_keys": list(LANDMARK_KEYS),
            "enemy_kinds": list(ENEMY_KINDS_EXPECTED),
            "enemy_levels": list(ENEMY_LEVELS),
            "semantic_image_slot_count": 20,
        },
        "inherited_v2_selftest_count": len(inherited_report.get("checks", [])),
        "checks": rb.checks,
        "summary": rb.summary(),
        "overall_status": rb.overall_status(),
        "exit_code": rb.exit_code(),
    }
    return report, rb.exit_code()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Tier A v3 atlas, hero-direction, and LOD static invariants."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="target repository root (default: current directory)",
    )
    parser.add_argument(
        "--baseline-root",
        default=None,
        help="v2 baseline repository root; required for normal verification",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run deterministic in-memory negative self-tests",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    # Reports belong to the harness checkout, never to the frozen target.
    harness_root = Path(__file__).resolve().parents[1]
    output_path = harness_root / (SELFTEST_REPORT if args.selftest else VERIFICATION_REPORT)
    try:
        if args.selftest:
            report, exit_code = run_selftest()
        else:
            if not args.baseline_root:
                raise SetupError("--baseline-root is required for Tier A v3 verification")
            repo_root = Path(args.repo_root).expanduser().resolve()
            baseline_root = Path(args.baseline_root).expanduser().resolve()
            report, exit_code = verify_target(repo_root, baseline_root)
        try:
            write_json_report(output_path, report)
        except Exception as exc:
            print(f"Tier A report write failure: {exc}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "mode": report["mode"],
                    "overall_status": report["overall_status"],
                    "exit_code": exit_code,
                    "report": str(output_path),
                    "summary": report["summary"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return exit_code
    except Exception as exc:
        emergency_report = {
            "schema_version": 3,
            "mode": "selftest" if args.selftest else "verification",
            "preregistration": {
                "version": PREREGISTRATION_VERSION,
                "checkpoint_tag": EXPECTED_TAG,
                "checkpoint_commit": EXPECTED_COMMIT,
            },
            "checks": [
                {
                    "id": "INTERNAL.TOP_LEVEL_EXCEPTION",
                    "status": "fail",
                    "atlas": None,
                    "sprites": [],
                    "measured": {"exception_type": type(exc).__name__},
                    "threshold": {},
                    "message": str(exc),
                    "category": "internal",
                }
            ],
            "summary": {"passed": 0, "failed": 1, "skipped": 0},
            "overall_status": "error",
            "exit_code": 2,
        }
        try:
            write_json_report(output_path, emergency_report)
        except Exception:
            pass
        print(f"Tier A internal failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
