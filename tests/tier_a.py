#!/usr/bin/env python3
"""Tier A deterministic atlas and hero-direction verifier.

Approved preregistration: Tier A 1.0-rc2
Target tag: tierA-hero-fix-v2
Target commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

Allowed runtime dependencies: Python standard library, Pillow, numpy, and
read-only Git commands. The target repository is never modified.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
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


PREREGISTRATION_VERSION = "1.0-rc2"
EXPECTED_TAG = "tierA-hero-fix-v2"
EXPECTED_COMMIT = "13dbea7deec6e5994501ffc5e70b47e9d0e24dcf"
TARGET_PROHIBITED_PATHS = (
    "preregistration.md",
    "tests/tier_a.py",
    "TIER_A_RUNBOOK.md",
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

VERIFICATION_REPORT = "tier_a_report.json"
SELFTEST_REPORT = "tier_a_selftest_report.json"


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
# Verification
# ---------------------------------------------------------------------------


def _checkpoint_preflight(repo_root: Path, rb: ReportBuilder) -> dict[str, Any]:
    target: dict[str, Any] = {
        "repo_root": str(repo_root.resolve()),
        "head_commit": None,
        "expected_tag_present": False,
        "tag_is_annotated": False,
        "tag_resolved_commit": None,
        "clean_before": False,
        "clean_after": None,
        "test_files_absent_from_target": False,
        "missing_required_paths": [],
        "prohibited_paths_present": [],
    }
    try:
        inside = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
        ok = inside == "true"
        rb.add(
            "SETUP.GIT_REPOSITORY",
            "pass" if ok else "fail",
            measured={"is_inside_work_tree": inside},
            threshold={"expected": "true"},
            category="checkpoint",
            message="" if ok else "target is not a Git worktree",
        )
        if not ok:
            return target

        head = str(run_git(repo_root, ["rev-parse", "HEAD"]))
        target["head_commit"] = head
        head_ok = head == EXPECTED_COMMIT
        rb.add(
            "SETUP.CHECKPOINT_HEAD",
            "pass" if head_ok else "fail",
            measured={"head_commit": head},
            threshold={"expected_commit": EXPECTED_COMMIT},
            category="checkpoint",
            message="" if head_ok else "HEAD does not match frozen checkpoint",
        )

        tag_type: str | None = None
        tag_commit: str | None = None
        try:
            tag_type = str(run_git(repo_root, ["cat-file", "-t", f"refs/tags/{EXPECTED_TAG}"]))
            tag_commit = str(run_git(repo_root, ["rev-parse", f"{EXPECTED_TAG}^{{commit}}"]))
        except SetupError:
            tag_type = None
            tag_commit = None
        target["expected_tag_present"] = tag_type is not None
        target["tag_is_annotated"] = tag_type == "tag"
        target["tag_resolved_commit"] = tag_commit
        tag_ok = tag_type == "tag" and tag_commit == EXPECTED_COMMIT and head == tag_commit
        rb.add(
            "SETUP.CHECKPOINT_TAG",
            "pass" if tag_ok else "fail",
            measured={
                "tag": EXPECTED_TAG,
                "object_type": tag_type,
                "resolved_commit": tag_commit,
                "head_commit": head,
            },
            threshold={
                "required_object_type": "tag",
                "required_commit": EXPECTED_COMMIT,
                "must_point_to_head": True,
            },
            category="checkpoint",
            message="" if tag_ok else "expected annotated tag is absent or resolves incorrectly",
        )

        status = str(run_git(repo_root, ["status", "--porcelain"]))
        clean = status == ""
        target["clean_before"] = clean
        rb.add(
            "SETUP.TARGET_CLEAN_BEFORE",
            "pass" if clean else "fail",
            measured={"status_porcelain": status.splitlines()},
            threshold={"expected_entries": 0},
            category="checkpoint",
            message="" if clean else "target worktree is not clean before verification",
        )

        tree_text = str(run_git(repo_root, ["ls-tree", "-r", "--name-only", "HEAD"]))
        tree_paths = set(tree_text.splitlines()) if tree_text else set()
        missing = sorted(set(REQUIRED_TARGET_PATHS) - tree_paths)
        prohibited = sorted(set(TARGET_PROHIBITED_PATHS) & tree_paths)
        target["missing_required_paths"] = missing
        target["prohibited_paths_present"] = prohibited
        target["test_files_absent_from_target"] = not prohibited
        rb.add(
            "SETUP.REQUIRED_INPUT_PATHS",
            "pass" if not missing else "fail",
            measured={"missing_paths": missing},
            threshold={"required_paths": list(REQUIRED_TARGET_PATHS)},
            category="checkpoint",
            message="" if not missing else "required committed inputs are missing",
        )
        rb.add(
            "SETUP.HARNESS_ABSENT_FROM_TARGET",
            "pass" if not prohibited else "fail",
            measured={"prohibited_paths_present": prohibited},
            threshold={"prohibited_paths": list(TARGET_PROHIBITED_PATHS)},
            category="checkpoint",
            message="" if not prohibited else "Tier A harness files are present in target tag",
        )
    except SetupError as exc:
        rb.add(
            "SETUP.GIT_COMMAND",
            "fail",
            measured={},
            threshold={},
            category="checkpoint",
            message=str(exc),
        )
    return target


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


def verify_target(repo_root: Path) -> tuple[dict[str, Any], int]:
    rb = ReportBuilder("verification")
    target = _checkpoint_preflight(repo_root, rb)
    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": "verification",
        "preregistration": {
            "version": PREREGISTRATION_VERSION,
            "checkpoint_tag": EXPECTED_TAG,
            "checkpoint_commit": EXPECTED_COMMIT,
        },
        "target": target,
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
        },
        "atlases": {},
        "sprites": {},
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

        html_bytes = git_blob(repo_root, "index.html")
        try:
            html = html_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SetupError(f"index.html is not valid UTF-8: {exc}") from exc

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
            },
            threshold={"unique_required_declarations": True},
            category="setup",
        )

        base_rects, base_summary = _rect_checks("base", base_manifest, base_image, rb)
        hi_rects, hi_summary = _rect_checks("hi", hi_manifest, hi_image, rb)
        report["atlases"]["base"] = base_summary
        report["atlases"]["hi"] = hi_summary

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

    except SetupError as exc:
        rb.add(
            "SETUP.EXTRACTION_OR_DEPENDENCY",
            "fail",
            measured={},
            threshold={},
            category="setup",
            message=str(exc),
        )
    except Exception as exc:  # defensive conversion to deterministic error report
        rb.add(
            "INTERNAL.UNEXPECTED_EXCEPTION",
            "fail",
            measured={"exception_type": type(exc).__name__},
            threshold={},
            category="internal",
            message=str(exc),
        )

    try:
        status_after = str(run_git(repo_root, ["status", "--porcelain"]))
        clean_after = status_after == ""
        target["clean_after"] = clean_after
        rb.add(
            "SETUP.TARGET_CLEAN_AFTER",
            "pass" if clean_after else "fail",
            measured={"status_porcelain": status_after.splitlines()},
            threshold={"expected_entries": 0},
            category="checkpoint",
            message="" if clean_after else "target worktree changed during verification",
        )
        head_after = str(run_git(repo_root, ["rev-parse", "HEAD"]))
        same_head = head_after == target.get("head_commit") == EXPECTED_COMMIT
        rb.add(
            "SETUP.TARGET_HEAD_UNCHANGED",
            "pass" if same_head else "fail",
            measured={"head_before": target.get("head_commit"), "head_after": head_after},
            threshold={"expected_commit": EXPECTED_COMMIT},
            category="checkpoint",
            message="" if same_head else "target HEAD changed during verification",
        )
    except SetupError as exc:
        rb.add(
            "SETUP.POST_RUN_INTEGRITY",
            "fail",
            measured={},
            threshold={},
            category="checkpoint",
            message=str(exc),
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


def run_selftest() -> tuple[dict[str, Any], int]:
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Tier A atlas and hero-direction invariants."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="target repository root (default: current directory)",
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
            repo_root = Path(args.repo_root).expanduser().resolve()
            report, exit_code = verify_target(repo_root)
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
            "schema_version": 1,
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
