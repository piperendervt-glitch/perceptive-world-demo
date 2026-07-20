# Tier A Test Preregistration

## 0. Document metadata

```yaml
document: preregistration.md
project: perceptive-world-demo
test_tier: Tier A
version: 1.0-rc2
status: approval-pending
checkpoint_tag: tierA-hero-fix-v2
checkpoint_type: annotated-tag
checkpoint_commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
test_branch: test/tier-a-v1
target_contains_test_harness: false
```

This document preregisters the Tier A acceptance criteria for the fixed `perceptive-world-demo` checkpoint identified by:

```text
tag:    tierA-hero-fix-v2
commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
```

This rc2 revision supersedes rc1 for Tier A verification of the v2 checkpoint.

The revision changes only:

1. the frozen checkpoint tag and commit;
2. the classification rules used to distinguish front-facing `down` sprites from right-facing `side` sprites.

The following remain frozen from rc1:

* static extraction rules;
* Invariants A1 through A9;
* the required 34 base sprite names;
* the `alpha > 0` opaque-pixel definition;
* the upper-50% head-region definition;
* the skin-color mask;
* `T_FACE = 0.08`;
* `T_NOFACE = 0.01`;
* the five-times down/up relative rule;
* the exit-code contract;
* determinism requirements;
* the machine-readable report contract;
* the negative self-test framework.

The rc1 side rule assumed that a correct side-facing sprite would contain less visible skin than a correct front-facing sprite. Measurements from the frozen assets showed that this assumption was structurally incorrect: front-facing and side-facing sprites both contain a clearly visible face and cannot reliably be separated by `face_ratio`.

rc2 therefore classifies `down` and `side` using the horizontal centroid of head-region skin pixels:

* `down`: visible face centered horizontally;
* `side`: visible face displaced toward the right-facing side.

The disclosed frozen-checkpoint measurements are used to document the structural defect in the rc1 classifier and to define the replacement classification axis. After approval of rc2, its thresholds must not be further adjusted merely to change the target result.

---

# 1. Purpose

Tier A verifies two classes of invariants against a fixed Git checkpoint:

1. Atlas consistency for both the base atlas and the HI atlas.
2. Hero-direction invariants that prevent recurrence of walking-direction sprite errors.

The test is intended to detect, at minimum:

* malformed embedded PNG data;
* sprite rectangles outside atlas bounds;
* overlapping atlas rectangles;
* missing required sprite names;
* inconsistent base and HI manifests;
* stale or mismatched disk-side HI build artifacts;
* missing hero frames;
* front-facing sprites placed in the `up` row;
* rear-facing sprites placed in the `down` row;
* off-center or right-facing sprites placed in the `down` row;
* front-facing, rear-facing, centered, or left-facing sprites placed in the `side` row;
* source side sprites that do not face right.

Tier A is not a general visual-quality test. It does not evaluate:

* gameplay behavior;
* browser rendering;
* animation timing;
* interpolation;
* CSS;
* JavaScript execution;
* artistic quality beyond the preregistered hero-direction pixel conditions.

---

# 2. Frozen checkpoint and test-harness separation

## 2.1 Target checkpoint

The only accepted Tier A rc2 target is:

```text
tierA-hero-fix-v2
```

The annotated tag must resolve to:

```text
13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
```

A normal verification run must fail before evaluating atlas contents when any of the following is true:

* the supplied repository is not a Git repository;
* `HEAD` cannot be resolved;
* `HEAD` is not `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf`;
* `tierA-hero-fix-v2^{commit}` does not resolve to that SHA;
* the expected tag does not point to the current `HEAD`;
* required committed input files are missing.

The exact tag and resolved commit SHA must be recorded in `tier_a_report.json`.

## 2.2 Test-harness separation

The following Tier A files must not be present in the frozen target tag:

```text
preregistration.md
tests/tier_a.py
TIER_A_RUNBOOK.md
```

They are maintained separately on:

```text
test/tier-a-v1
```

The frozen tag contains implementation and asset files only.

The normal deployment model is therefore:

```text
parent/
├─ perceptive-world-demo-tierA-target/
│  └─ detached checkout of tierA-hero-fix-v2
│
└─ perceptive-world-demo-tierA-harness/
   ├─ preregistration.md
   ├─ TIER_A_RUNBOOK.md
   └─ tests/
      └─ tier_a.py
```

The Tier A script is executed from the harness checkout and receives the target repository root as an argument.

Normative command:

```bash
python tests/tier_a.py <target-repository-root>
```

Example:

```bash
python tests/tier_a.py ../perceptive-world-demo-tierA-target
```

## 2.3 Committed-files-only policy

Only files committed at the target `HEAD` may affect the result.

The test must not read target data directly from mutable working-tree files when Git can provide the committed blob.

Normative input access is equivalent to:

```bash
git -C <target-root> show HEAD:index.html
git -C <target-root> show HEAD:assets/hi/manifest_hi.json
git -C <target-root> show HEAD:assets/hi/atlas_hi.png
```

Binary files must be read as raw bytes from the committed Git object.

Untracked or modified target files must not affect extracted manifests, atlas data, or the final decision.

The target working-tree status must still be reported. A non-clean target worktree is a checkpoint-integrity failure, even though committed blobs are used for the actual inspection.

---

# 3. Execution constraints

Tier A must be:

* browser-independent;
* deterministic;
* offline;
* repeatable;
* static;
* independent of runtime JavaScript evaluation.

Permitted dependencies:

```text
Python 3
Python standard library
Pillow
numpy
Git command-line read operations
```

Prohibited mechanisms and dependencies:

```text
headless browsers
browser automation
runtime JavaScript evaluation
Node.js
SciPy
OpenCV
ImageMagick
network access
external downloads
runtime asset generation
tools/conform.py execution
tools/conform_hi.py execution
manual visual judgment as an automated pass condition
```

The test must not modify:

* the target repository;
* the target tag;
* target assets;
* target manifests;
* `index.html`;
* preregistered thresholds.

---

# 4. Authoritative and auxiliary inputs

## 4.1 Authoritative runtime source

The committed `index.html` is the sole authoritative source for data that the game actually renders.

The test extracts the following values statically:

```javascript
const SPR={...};
const SPR_HI={...};

ATLAS.src="data:image/png;base64,...";
ATLAS_HI.src="data:image/png;base64,...";
```

The inline values are authoritative:

* `SPR` is the base manifest.
* `SPR_HI` is the HI manifest.
* `ATLAS` is the base atlas PNG.
* `ATLAS_HI` is the HI atlas PNG.

JavaScript must not be executed to obtain them.

## 4.2 Auxiliary HI build artifacts

The following committed files are auxiliary consistency artifacts:

```text
assets/hi/manifest_hi.json
assets/hi/atlas_hi.png
```

They are not authoritative over `index.html`.

A discrepancy means the generated disk artifact and the embedded runtime artifact are out of sync. Such a discrepancy is a Tier A failure.

No base-atlas disk comparison is part of Tier A rc2 unless added by a future preregistration revision.

---

# 5. Static extraction rules

## 5.1 Manifest extraction

The test must extract exactly one declaration for each of:

```text
const SPR=
const SPR_HI=
```

Whitespace between tokens may be tolerated. For example, the following forms are equivalent:

```javascript
const SPR={...};
const SPR = {...};
const   SPR_HI = {...};
```

For each declaration:

1. Locate the declaration.
2. Read the text after `=`.
3. Stop at the declaration’s terminating semicolon.
4. Parse the extracted text with Python’s standard JSON parser.
5. Require a top-level JSON object.

The extracted object must be valid JSON, not merely valid JavaScript.

The following are invalid:

* comments inside the value;
* functions;
* expressions;
* computed properties;
* trailing commas not accepted by JSON;
* duplicate or ambiguous declarations;
* a missing terminating semicolon;
* a non-object top-level value.

Extraction failure is a Tier A failure.

## 5.2 Embedded atlas extraction

The test must extract exactly one assignment for each of:

```text
ATLAS.src
ATLAS_HI.src
```

Each value must begin with:

```text
data:image/png;base64,
```

The payload after the comma is decoded using strict base64 validation.

Requirements:

* the base64 text is valid;
* the decoded bytes are accepted by Pillow;
* Pillow identifies the input format as PNG;
* the PNG can be fully decoded;
* width and height are positive;
* a reopened copy can be converted to RGBA.

Malformed, missing, duplicated, ambiguous, truncated, or non-PNG embedded data is a failure.

---

# 6. Manifest entry model

Each manifest entry must map a sprite name to an object containing:

```json
{
  "x": 0,
  "y": 0,
  "w": 1,
  "h": 1
}
```

The coordinate fields must be JSON integers.

Boolean values are not accepted as integers, even though Python treats `bool` as a subclass of `int`.

Required fields:

```text
x
y
w
h
```

Additional fields do not affect Tier A rectangle calculations.

Sprite rectangles use half-open coordinates:

```text
[x, x + w) × [y, y + h)
```

Accordingly:

* touching edges are allowed;
* touching corners are allowed;
* atlas padding between rectangles is allowed;
* positive-area intersection is not allowed.

---

# 7. Required base-sprite coverage

The following 34 names are the complete Tier A rc2 required-name list:

```text
grass
dirt
water
flower

hero_down_0
hero_down_1
hero_down_2

hero_up_0
hero_up_1
hero_up_2

hero_side_0
hero_side_1
hero_side_2

tree
well
shrine
torch
house
goblin
sentry
chief

ifloor
iwall
idoor

npc_elder
npc_herb

table
chair
shelf
bed
plant
barrel
cauldron
rug
```

Category count:

```text
terrain:                    4
hero:                       9
nature/building/enemy:      8
interior structure:         3
NPC:                        2
furniture:                  8
total:                     34
```

All 34 names must exist in `SPR`.

Additional names in `SPR` are permitted.

The required-name list, not the total number of entries in the current manifest, is the source of truth for coverage.

Any future addition or removal from this required list requires a preregistration revision.

---

# 8. Invariant A: atlas consistency

Invariant A applies separately to the base and HI atlases, except where a check explicitly applies to only one.

## A1. Rectangle value validity

For every entry in `SPR` and `SPR_HI`:

```text
x >= 0
y >= 0
w > 0
h > 0
```

All four values must be non-boolean integers.

The report must identify:

* atlas;
* sprite name;
* offending field;
* measured value;
* required condition.

## A2. Rectangle containment

For every manifest entry:

```text
x + w <= atlas_width
y + h <= atlas_height
```

The report must include:

* atlas width and height;
* sprite rectangle;
* calculated right edge;
* calculated bottom edge;
* offending sprite name.

## A3. Embedded PNG validity and total containment

Both embedded atlas payloads must:

* decode from strict base64;
* be valid PNG data;
* have positive dimensions;
* decode completely through Pillow;
* contain all rectangles in the corresponding manifest.

The report must include:

```text
atlas_width
atlas_height
max_manifest_right
max_manifest_bottom
```

where:

```text
max_manifest_right  = max(x + w)
max_manifest_bottom = max(y + h)
```

An empty manifest is a failure.

## A4. Rectangle non-overlap

For any two distinct rectangles `a` and `b`, overlap exists when both conditions are true:

```text
max(a.x, b.x) < min(a.x + a.w, b.x + b.w)
max(a.y, b.y) < min(a.y + a.h, b.y + b.h)
```

No two rectangles in the same manifest may overlap.

Edge or corner contact is not overlap.

The report must list every overlapping pair in deterministic sprite-name order and include the positive-area intersection rectangle.

## A5. Required base-name coverage

Every name in the fixed 34-name list must exist in `SPR`.

Missing names cause failure.

Additional names do not cause failure.

The report must include:

```text
required_count
present_required_count
missing_names
additional_names
```

## A6. HI subset consistency

Every key in `SPR_HI` must also exist in `SPR`:

```text
keys(SPR_HI) ⊆ keys(SPR)
```

Any HI-only name is a failure.

The report must identify every HI-only key.

The fact that `SPR_HI` contains only a subset of normal sprites is otherwise valid.

## A7. Inline HI manifest versus disk manifest

The parsed inline `SPR_HI` object must equal the parsed committed file:

```text
assets/hi/manifest_hi.json
```

Comparison uses structural JSON equality.

The following formatting differences are ignored:

* indentation;
* spaces;
* line endings;
* final newline;
* JSON object key order.

The following are failures:

* missing disk manifest;
* invalid JSON;
* a missing key;
* an additional key;
* a differing coordinate;
* a differing value;
* a differing nested structure.

The report must summarize the structural difference in deterministic order.

## A8. Inline HI atlas versus disk atlas

The decoded inline `ATLAS_HI` image must equal the committed file:

```text
assets/hi/atlas_hi.png
```

Both images must be decoded and converted to RGBA.

Equality requires both:

```text
same width and height
same RGBA value at every pixel
```

Comparison must not use:

* PNG file-byte equality;
* compressed-stream equality;
* metadata equality;
* file SHA equality as the substantive image test.

PNG compression level, chunk order, and metadata may differ without failure when the decoded RGBA images are identical.

The following are failures:

* missing disk image;
* invalid disk PNG;
* dimension mismatch;
* one or more differing RGBA pixels.

The report must include:

* inline dimensions;
* disk dimensions;
* differing-pixel count;
* first differing pixel in deterministic row-major order;
* inline RGBA at that pixel;
* disk RGBA at that pixel.

The inline `ATLAS_HI` remains the authoritative runtime value. Failure indicates an out-of-sync build artifact.

## A9. Hero-frame presence in both manifests

The following nine keys must exist in both `SPR` and `SPR_HI`:

```text
hero_down_0
hero_down_1
hero_down_2
hero_up_0
hero_up_1
hero_up_2
hero_side_0
hero_side_1
hero_side_2
```

Missing any one of these keys from either manifest is a failure.

The normal base-fallback behavior for non-HI sprites does not apply to the Tier A hero-direction test.

No hero frame may be substituted from the other atlas.

---

# 9. Invariant B: hero direction

Invariant B evaluates all nine hero frames independently in:

```text
base atlas using SPR
HI atlas using SPR_HI
```

This produces 18 measured hero sprite records.

All direction checks operate on decoded source pixels. The test does not:

* resize sprites;
* interpolate pixels;
* mirror sprites;
* apply browser scaling;
* evaluate runtime JavaScript;
* use the base sprite as an HI fallback.

## 9.1 Hero crop

Each hero sprite is cropped using its corresponding manifest rectangle:

```text
[x, x + w) × [y, y + h)
```

The resulting crop must have exactly:

```text
width  = w
height = h
```

Any mismatch is a failure.

## 9.2 Opaque-pixel definition

A pixel is considered opaque when:

```text
alpha > 0
```

Partially transparent antialiasing pixels are included.

A hero sprite containing no opaque pixels is a failure.

## 9.3 Opaque bounding box

The opaque bounding box is the smallest half-open rectangle containing all pixels for which:

```text
alpha > 0
```

It is represented as:

```text
[left, top, right, bottom)
```

with:

```text
bbox_width  = right - left
bbox_height = bottom - top
```

A zero-width or zero-height bounding box is a failure.

## 9.4 Head region

The head region is the upper 50% of the opaque bounding box.

Fixed constant:

```text
HEAD_REGION_FRACTION = 0.50
```

The lower boundary is:

```text
head_bottom = top + ceil(0.50 × bbox_height)
```

The head region is:

```text
x: left <= x < right
y: top  <= y < head_bottom
```

This means the upper approximately one-half of the opaque bounding box.

It does not mean a narrow band between the 45% and 55% height positions.

The same formula is used for base and HI sprites.

## 9.5 Skin-color mask

A pixel is classified as skin when all of the following are true:

```text
alpha > 0
R > 185
140 < G < 205
110 < B < 180
R > G
G > B
```

All channels are decoded 8-bit RGBA integer values.

No color-space conversion, image filtering, tolerance expansion, or target-specific calibration is applied.

## 9.6 Face ratio

For each hero sprite:

```text
head_opaque_pixels =
    number of head-region pixels with alpha > 0

head_skin_pixels =
    number of head-region pixels satisfying the skin mask
```

The face ratio is:

```text
face_ratio = head_skin_pixels / head_opaque_pixels
```

If:

```text
head_opaque_pixels == 0
```

the sprite fails.

The following raw values must be written to the report:

```text
head_opaque_pixels
head_skin_pixels
face_ratio
```

The unrounded floating-point ratio is used for the actual comparison.

Rounded display values must not affect pass or fail.

## 9.7 Normalized horizontal skin centroid

For every `down` and `side` frame, calculate the horizontal centroid of all skin pixels inside the head region.

For a skin pixel at crop-coordinate `x`, define its horizontal pixel center as:

```text
pixel_center_x = x + 0.5
```

Then calculate:

```text
skin_centroid_x =
    mean(pixel_center_x for all head-region skin pixels)
```

Normalize it relative to the full opaque bounding box:

```text
normalized_skin_centroid_x =
    (skin_centroid_x - bbox_left) / bbox_width
```

The comparison center is the horizontal center of the full opaque bounding box.

It is not:

* the center of the full manifest rectangle;
* the center of the head-region rectangle after excluding transparency;
* the center of a skin-only bounding box;
* a browser-scaled coordinate.

A `down` or `side` frame with no head-region skin pixels cannot produce a valid centroid and fails its applicable direction rule.

The centroid definition is unchanged from rc1. rc2 expands its use from side-facing frames to both down-facing and side-facing classification.

---

# 10. Fixed direction thresholds

The preregistered constants are:

```text
T_FACE          = 0.08
T_NOFACE        = 0.01
T_DOWN_UP_RATIO = 5.0
T_CENTER        = 0.05
T_SIDE_RIGHT    = 0.57
```

`T_FACE`, `T_NOFACE`, and `T_DOWN_UP_RATIO` are unchanged from rc1.

The former constant:

```text
T_RIGHT_CENTER = 0.50
```

is removed.

It is replaced by:

* `T_CENTER = 0.05`, defining the maximum permitted distance of a down-facing skin centroid from horizontal center;
* `T_SIDE_RIGHT = 0.57`, defining the exclusive lower boundary for a right-facing side centroid.

The fixed direction rules are:

```text
up:
    face_ratio <= 0.01

down:
    face_ratio >= 0.08
    and
    abs(normalized_skin_centroid_x - 0.50) <= 0.05

side:
    face_ratio >= 0.08
    and
    normalized_skin_centroid_x > 0.57

relative:
    down_face_ratio >= 5.0 * up_face_ratio
```

The down centroid interval is inclusive:

```text
0.45 <= normalized_skin_centroid_x <= 0.55
```

The side centroid boundary is exclusive:

```text
normalized_skin_centroid_x > 0.57
```

Therefore:

```text
normalized_skin_centroid_x == 0.57
```

is a side-direction failure.

There is no upper `face_ratio` limit for side-facing sprites in rc2.

## 10.1 Reason for replacing the rc1 side rule

The rc1 classifier used:

```text
side:
    0.01 < face_ratio < 0.08
```

This encoded the assumption that visible face quantity should form an ordered progression:

```text
up < side < down
```

That assumption is not structurally valid for these sprites.

A correctly drawn right-facing side profile may expose a large contiguous skin region. Its normalized skin area may equal or approach that of a front-facing sprite.

The frozen-tag measurements show:

```text
down:
    face_ratio                 0.187–0.210
    normalized skin centroid  0.495–0.506

up:
    face_ratio                 0.002–0.006

side:
    face_ratio                 0.160–0.168
    normalized skin centroid  0.635–0.641
```

The correct `down` and `side` sprites therefore overlap substantially on `face_ratio`.

They are cleanly separated by horizontal skin centroid:

```text
down centroid: approximately 0.50
side centroid: approximately 0.64
separation:    approximately 0.13
```

The structural classifier is therefore:

```text
face presence:
    separates up from down/side

horizontal skin centroid:
    separates centered down from right-facing side
```

## 10.2 Threshold rationale

### Face-presence thresholds

`T_NOFACE = 0.01` remains the no-face threshold.

It permits a small amount of antialiasing or edge-color contamination while remaining close to the rear-facing measurements:

```text
up face_ratio: 0.002–0.006
```

`T_FACE = 0.08` remains the visible-face threshold.

Both correct front-facing and correct side-facing sprites must satisfy it.

### Down centering threshold

The observed correct down centroids are:

```text
0.495–0.506
```

`T_CENTER = 0.05` defines the inclusive centered interval:

```text
0.45–0.55
```

This permits modest frame-to-frame asymmetry and antialiasing variation while rejecting clearly right-displaced side profiles.

### Side rightward threshold

The observed separation between correct down and correct side centroids is approximately:

```text
0.13
```

The midpoint between approximately `0.50` and approximately `0.64` is approximately:

```text
0.57
```

`T_SIDE_RIGHT = 0.57` places the decision boundary near that midpoint, leaving substantial separation from both observed classes.

The threshold is not intended to encode an exact target value. It expresses the general directional property that the visible skin of a right-facing profile is displaced toward the right side of the opaque head/body bounding box.

The boundary is exclusive so that a fixture exactly on the decision boundary is not accepted as demonstrably right-facing.

## 10.3 Revision classification

This rc2 change is a §19 preregistration revision, not an in-place relaxation of a valid classifier.

The old classifier used the wrong separating variable.

rc2 replaces:

```text
side has an intermediate quantity of visible skin
```

with:

```text
side has a visible face whose skin centroid is displaced
toward the direction the profile faces
```

After approval of rc2, the new thresholds and operators are frozen for the v2 checkpoint.

---

# 11. Direction-specific rules

## B1. Down-facing frames

Each of the following must satisfy the down-facing rule:

```text
hero_down_0
hero_down_1
hero_down_2
```

Both conditions are mandatory:

```text
face_ratio >= T_FACE
```

and:

```text
abs(normalized_skin_centroid_x - 0.50) <= T_CENTER
```

Equivalent fixed conditions:

```text
face_ratio >= 0.08
```

and:

```text
abs(normalized_skin_centroid_x - 0.50) <= 0.05
```

The centroid condition is equivalently:

```text
0.45 <= normalized_skin_centroid_x <= 0.55
```

Each frame must pass independently in each atlas.

An average across the three frames cannot compensate for a failing frame.

A frame with sufficient skin but a strongly right-displaced centroid is not accepted as down-facing.

A frame with a centered centroid but insufficient visible skin is also not accepted as down-facing.

## B2. Up-facing frames

Each of the following must satisfy the up-facing rule:

```text
hero_up_0
hero_up_1
hero_up_2
```

Required condition:

```text
face_ratio <= T_NOFACE
```

Equivalent fixed condition:

```text
face_ratio <= 0.01
```

Each frame must pass independently in each atlas.

No centroid condition is required for an up-facing frame.

## B3. Side-facing visible-face rule

Each of the following must contain a clearly visible face:

```text
hero_side_0
hero_side_1
hero_side_2
```

Required condition:

```text
face_ratio >= T_FACE
```

Equivalent fixed condition:

```text
face_ratio >= 0.08
```

There is no upper `face_ratio` threshold for side-facing sprites.

A side-facing sprite may contain an amount of detected skin comparable to a front-facing sprite.

Each frame must pass independently in each atlas.

## B4. Side-facing rightward-centroid rule

Each side-facing frame must additionally satisfy:

```text
normalized_skin_centroid_x > T_SIDE_RIGHT
```

Equivalent fixed condition:

```text
normalized_skin_centroid_x > 0.57
```

Equality with `0.57` is a failure.

This condition establishes that the source side sprite faces right.

Runtime left-facing movement may be produced by horizontal reflection, but the source atlas must remain right-facing.

A side frame fails when:

* it has no valid head-region skin centroid;
* its centroid is centered;
* its centroid is left of center;
* its centroid is at or below the `0.57` boundary.

## B5. Relative down-versus-up condition

For each atlas and each matching animation index:

```text
i ∈ {0, 1, 2}
```

the corresponding down frame must satisfy:

```text
face_ratio(hero_down_i)
    >=
5.0 × face_ratio(hero_up_i)
```

The pairs are:

```text
hero_down_0 versus hero_up_0
hero_down_1 versus hero_up_1
hero_down_2 versus hero_up_2
```

This is evaluated in addition to the absolute down and up thresholds.

No division is required. The comparison is performed by multiplication:

```text
down_face_ratio >= 5.0 * up_face_ratio
```

When the up ratio is zero, the relative comparison alone is trivially satisfied, but the down frame must still independently pass:

```text
face_ratio >= 0.08
```

and:

```text
abs(normalized_skin_centroid_x - 0.50) <= 0.05
```

---

# 12. Check granularity and failure behavior

Checks must be recorded at a granularity that identifies the offending atlas and sprite.

Examples:

```text
A1.RECT_VALID.BASE.hero_down_0
A2.BOUNDS.HI.hero_side_1
B1.DOWN_FACE.BASE.hero_down_2
B1.DOWN_CENTER.BASE.hero_down_2
B2.UP_NOFACE.HI.hero_up_1
B3.SIDE_FACE.BASE.hero_side_0
B4.SIDE_RIGHT.BASE.hero_side_0
B5.DOWN_UP_RELATIVE.HI.index_2
```

A failure in one check should not prevent unrelated checks from running when sufficient data remains available.

For example:

* a failing hero direction must not suppress overlap reporting;
* an HI disk-atlas mismatch must not suppress inline hero measurements;
* one missing sprite should not suppress checks for other present sprites.

A prerequisite failure may cause dependent checks to be recorded as failed or not evaluable, but it must not be silently ignored.

Examples of prerequisite failures:

* the embedded atlas cannot be decoded;
* a required sprite rectangle is missing;
* a crop has no opaque pixels;
* a required centroid cannot be calculated.

No failed check may be converted to `skip` solely because it would make the overall result pass.

---

# 13. Negative self-test requirements

The command:

```bash
python tests/tier_a.py --selftest
```

must execute deterministic, entirely in-memory negative tests.

The self-test must not depend on:

* the frozen target repository;
* target atlas contents;
* target worktree state;
* network access;
* browser behavior;
* generated files from previous runs.

Each negative test starts from a known-valid synthetic fixture and deliberately introduces one targeted fault.

The self-test passes only when every targeted fault is rejected by the intended checker.

## 13.1 A1 negative: invalid rectangle values

Mutations must demonstrate detection of:

```text
x < 0
y < 0
w <= 0
h <= 0
non-integer coordinate
boolean coordinate
```

Each mutation must be rejected by rectangle-value validation.

## 13.2 A2 negative: atlas bounds overflow

Move or resize an otherwise valid rectangle so that at least one condition is true:

```text
x + w > atlas_width
y + h > atlas_height
```

The bounds checker must reject it.

## 13.3 A3 negative: invalid embedded PNG

At minimum, test:

```text
invalid strict base64
valid base64 containing non-PNG bytes
corrupted or truncated PNG bytes
```

The embedded-PNG checker must reject each invalid fixture.

## 13.4 A4 negative: rectangle overlap

Move two otherwise valid rectangles so they overlap by at least one pixel in both axes.

The overlap checker must reject the fixture and identify the overlapping pair.

A control case where rectangles only touch at an edge must remain accepted.

## 13.5 A5 negative: missing required base sprite

Remove one name from an otherwise complete 34-name base manifest.

The coverage checker must fail and report the removed name.

## 13.6 A6 negative: HI-only sprite

Add a key to `SPR_HI` that does not exist in `SPR`.

The HI-subset checker must fail and report the HI-only key.

## 13.7 A7 negative: manifest mismatch

Change one coordinate in the in-memory disk-side HI manifest while leaving the inline manifest unchanged.

The structural equality checker must fail.

Formatting-only differences must remain accepted.

## 13.8 A8 negative: atlas RGBA mismatch

Create an in-memory auxiliary HI image with the same dimensions as the inline image, then change exactly one RGBA channel at one pixel.

The pixel-equality checker must fail.

A separate fixture must change the image dimensions and must also fail.

A fixture with identical RGBA pixels but different simulated PNG encoding metadata must remain accepted at the decoded-image comparison level.

## 13.9 A9 negative: missing hero frame

Test both cases independently:

```text
remove one required hero frame from SPR
remove one required hero frame from SPR_HI
```

The hero-presence checker must fail in both cases.

## 13.10 B1 negative: invalid down classification

The down negative tests must cover both mandatory dimensions of the down classifier.

### B1a. Insufficient visible face

Construct a valid synthetic hero crop satisfying:

```text
face_ratio < 0.08
```

and evaluate it as a down frame.

The down-facing checker must reject it.

The fixture should include a boundary case just below `0.08`.

### B1b. Right-displaced face

Construct a valid synthetic hero crop satisfying:

```text
face_ratio >= 0.08
```

and approximately:

```text
normalized_skin_centroid_x ≈ 0.64
```

Evaluate it as a down frame.

The visible-face condition must pass, but the down-centering condition must reject it because:

```text
abs(normalized_skin_centroid_x - 0.50) > 0.05
```

This negative test proves that a correct-looking right-facing profile cannot be accepted as down-facing merely because it contains sufficient skin.

Boundary coverage must also demonstrate:

```text
normalized_skin_centroid_x < 0.45
```

or:

```text
normalized_skin_centroid_x > 0.55
```

is rejected.

The inclusive valid boundaries:

```text
normalized_skin_centroid_x == 0.45
normalized_skin_centroid_x == 0.55
```

must remain accepted when the face-ratio condition passes.

## 13.11 B2 negative: up frame with visible face

Construct a valid synthetic hero crop satisfying:

```text
face_ratio > 0.01
```

and evaluate it as an up frame.

The up-facing checker must reject it.

The fixture should include a boundary case just above `0.01`.

The unchanged valid boundary:

```text
face_ratio == 0.01
```

must remain accepted as up-facing.

## 13.12 B3/B4 negative: invalid side classification

The side negative tests must jointly verify the visible-face and rightward-centroid requirements.

### B3a. Insufficient visible face

Construct or mutate a side fixture so:

```text
face_ratio < 0.08
```

The side visible-face checker must reject it.

The test must include:

```text
face_ratio <= T_NOFACE
```

to represent a rear-facing or effectively faceless sprite.

A boundary case just below `0.08` must fail.

The valid boundary:

```text
face_ratio == 0.08
```

must pass the face-presence part of the side rule when the centroid condition also passes.

### B4a. Centered or leftward face

Construct a side fixture satisfying:

```text
face_ratio >= 0.08
```

but:

```text
normalized_skin_centroid_x < 0.57
```

The side rightward-centroid checker must reject it.

This fixture represents a front-facing, centered, or left-facing sprite incorrectly evaluated as right-facing side material.

### B4b. Exact centroid boundary

Construct a side fixture satisfying:

```text
face_ratio >= 0.08
```

and:

```text
normalized_skin_centroid_x == 0.57
```

The side rightward-centroid checker must reject it.

This proves that the normative side comparison is:

```text
normalized_skin_centroid_x > 0.57
```

rather than:

```text
normalized_skin_centroid_x >= 0.57
```

### B4c. Valid positive control

A side fixture satisfying:

```text
face_ratio >= 0.08
```

and:

```text
normalized_skin_centroid_x > 0.57
```

must be accepted.

The positive control should use a clearly right-displaced value, such as approximately `0.64`, rather than relying only on a floating-point value infinitesimally above the boundary.

## 13.13 B5 negative: insufficient down/up separation

Construct corresponding down and up measurements satisfying:

```text
down_face_ratio < 5.0 * up_face_ratio
```

The relative checker must reject the pair.

The negative fixture must exercise the relative-comparison function directly and must not be accepted merely because another direction check would also fail.

## 13.14 Self-test result contract

The self-test exits zero only when:

* every valid baseline fixture is accepted;
* every intentionally damaged fixture is rejected;
* each rejection is attributed to the intended checker;
* no unexpected exception occurs;
* the self-test report is written successfully.

The self-test writes:

```text
tier_a_selftest_report.json
```

It must not overwrite:

```text
tier_a_report.json
```

---

# 14. Normal verification output contract

The normal command writes:

```text
tier_a_report.json
```

The file must be:

* UTF-8 JSON;
* machine-readable;
* deterministic;
* written with stable key ordering;
* written with stable check ordering;
* written with stable sprite ordering.

The report must be attempted even when one or more checks fail.

A report-write failure is a nonzero test result.

## 14.1 Required top-level fields

At minimum:

```json
{
  "schema_version": 1,
  "mode": "verification",
  "preregistration": {
    "version": "1.0-rc2",
    "checkpoint_tag": "tierA-hero-fix-v2",
    "checkpoint_commit": "13dbea7deec6e5994501ffc5e70b47e9d0e24dcf"
  },
  "target": {
    "repo_root": "",
    "head_commit": "",
    "expected_tag_present": false,
    "tag_resolved_commit": "",
    "clean_before": false,
    "clean_after": false,
    "test_files_absent_from_target": false
  },
  "thresholds": {},
  "atlases": {},
  "sprites": {},
  "checks": [],
  "summary": {
    "passed": 0,
    "failed": 0,
    "skipped": 0
  },
  "overall_status": "pass",
  "exit_code": 0
}
```

## 14.2 Required check record fields

Each check record must include at least:

```json
{
  "id": "B1.DOWN_FACE.BASE.hero_down_0",
  "status": "pass",
  "atlas": "base",
  "sprites": [
    "hero_down_0"
  ],
  "measured": {
    "face_ratio": 0.0,
    "normalized_skin_centroid_x": 0.0
  },
  "threshold": {
    "face_ratio": {
      "operator": ">=",
      "value": 0.08
    },
    "centroid_distance": {
      "operator": "<=",
      "center": 0.5,
      "value": 0.05
    }
  },
  "message": ""
}
```

Allowed check statuses:

```text
pass
fail
skip
```

Mandatory checks must not be marked `skip` merely because their input is inconvenient or produces an unfavorable result.

## 14.3 Required atlas measurements

For each atlas:

```text
decoded width
decoded height
manifest entry count
maximum right extent
maximum bottom extent
invalid rectangles
out-of-bounds rectangles
overlapping rectangle pairs
```

For HI auxiliary comparisons:

```text
inline/disk manifest equality
inline image dimensions
disk image dimensions
differing RGBA pixel count
first differing pixel, when applicable
```

## 14.4 Required hero measurements

For every hero frame in both atlases:

```text
atlas name
sprite name
manifest rectangle
crop width
crop height
opaque bounding box
head-region rectangle
head opaque-pixel count
head skin-pixel count
face ratio
normalized skin centroid X, when applicable
direction
associated check IDs
final sprite status
```

Measured integer values must be preserved exactly.

Floating-point values used for comparisons must be stored with sufficient precision to reproduce the decision.

---

# 15. Exit-code contract

Normal verification:

```text
exit 0:
all mandatory checks pass and report writing succeeds

exit 1:
one or more preregistered invariants fail

exit 2:
setup, checkpoint-integrity, extraction, dependency,
internal execution, or report-writing failure
```

Self-test:

```text
exit 0:
all positive controls pass and all negative fixtures
are rejected by their intended checkers

exit 1:
one or more self-test expectations fail

exit 2:
self-test setup, internal execution, or report-writing failure
```

Any nonzero result means the Tier A acceptance condition has not been met.

The JSON report’s `exit_code` and `overall_status` must agree with the process exit code.

---

# 16. Determinism requirements

For the same frozen checkpoint and the same Tier A implementation:

* the same checks must run;
* the same measurements must be produced;
* checks must appear in the same order;
* sprite records must appear in the same order;
* overlap pairs must appear in the same order;
* mismatch summaries must appear in the same order;
* JSON key ordering must remain stable;
* no timestamp may affect pass/fail or substantive report contents;
* no randomness may affect fixtures or measurements.

If timestamps are included for operational logging, they must not be used in equality comparisons or acceptance decisions.

---

# 17. Overall acceptance criteria

The fixed checkpoint passes Tier A only when all of the following are true:

1. The target repository is at commit:

   ```text
   13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
   ```

2. The annotated tag:

   ```text
   tierA-hero-fix-v2
   ```

   resolves to that commit.

3. The target worktree is clean before and after execution.

4. The target tag does not contain:

   ```text
   preregistration.md
   tests/tier_a.py
   TIER_A_RUNBOOK.md
   ```

5. All required committed input files are present.

6. All base and HI atlas rectangles are valid.

7. All rectangles fit inside their corresponding atlas.

8. Both inline atlas payloads decode as valid PNGs.

9. No rectangles overlap within either manifest.

10. All fixed 34 base sprite names exist.

11. Every HI key also exists in the base manifest.

12. Inline `SPR_HI` equals `assets/hi/manifest_hi.json`.

13. Inline `ATLAS_HI` equals `assets/hi/atlas_hi.png` after RGBA decoding and dimension comparison.

14. All nine hero frames exist in both `SPR` and `SPR_HI`.

15. Every down frame in both atlases satisfies both:

    ```text
    face_ratio >= 0.08
    ```

    and:

    ```text
    abs(normalized_skin_centroid_x - 0.50) <= 0.05
    ```

16. Every up frame in both atlases satisfies:

    ```text
    face_ratio <= 0.01
    ```

17. Every side frame in both atlases satisfies:

    ```text
    face_ratio >= 0.08
    ```

18. Every side frame in both atlases satisfies:

    ```text
    normalized_skin_centroid_x > 0.57
    ```

19. Every corresponding down/up pair in both atlases satisfies:

    ```text
    down_face_ratio >= 5.0 * up_face_ratio
    ```

20. Every preregistered negative self-test successfully proves that its corresponding checker rejects an intentionally damaged fixture.

21. The normal report and self-test report are valid JSON.

22. Both normal verification and self-test exit with code `0`.

A visual judgment that the sprites appear correct does not replace these machine-readable acceptance conditions.

---

# 18. Frozen constants

```yaml
checkpoint:
  tag: tierA-hero-fix-v2
  type: annotated-tag
  commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

harness:
  branch: test/tier-a-v1
  included_in_target_tag: false
  prohibited_target_paths:
    - preregistration.md
    - tests/tier_a.py
    - TIER_A_RUNBOOK.md

required_base_sprites:
  count: 34
  names:
    - grass
    - dirt
    - water
    - flower
    - hero_down_0
    - hero_down_1
    - hero_down_2
    - hero_up_0
    - hero_up_1
    - hero_up_2
    - hero_side_0
    - hero_side_1
    - hero_side_2
    - tree
    - well
    - shrine
    - torch
    - house
    - goblin
    - sentry
    - chief
    - ifloor
    - iwall
    - idoor
    - npc_elder
    - npc_herb
    - table
    - chair
    - shelf
    - bed
    - plant
    - barrel
    - cauldron
    - rug

rectangle_model:
  coordinate_interval: half-open
  coordinate_type: integer-excluding-boolean
  x_minimum: 0
  y_minimum: 0
  width_minimum_exclusive: 0
  height_minimum_exclusive: 0
  touching_edges_are_overlap: false

opaque_pixel:
  alpha_operator: ">"
  alpha_value: 0

head_region:
  fraction: 0.50
  origin: opaque-bbox-top
  lower_boundary: "top + ceil(0.50 * bbox_height)"
  interval: "top <= y < top + ceil(0.50 * bbox_height)"
  horizontal_interval: "bbox_left <= x < bbox_right"

skin_mask:
  alpha: "alpha > 0"
  red: "R > 185"
  green: "140 < G < 205"
  blue: "110 < B < 180"
  ordering: "R > G > B"

direction_thresholds:
  T_FACE: 0.08
  T_NOFACE: 0.01
  T_DOWN_UP_RATIO: 5.0
  T_CENTER: 0.05
  T_SIDE_RIGHT: 0.57

direction_rules:
  up: "face_ratio <= 0.01"
  down_face: "face_ratio >= 0.08"
  down_center: "abs(normalized_skin_centroid_x - 0.50) <= 0.05"
  side_face: "face_ratio >= 0.08"
  side_right: "normalized_skin_centroid_x > 0.57"
  relative: "down_face_ratio >= 5.0 * up_face_ratio"

hero_presence:
  required_in_base: true
  required_in_hi: true
  count_per_atlas: 9
  hi_fallback_allowed: false

auxiliary_hi_checks:
  inline_manifest_path: index.html::SPR_HI
  disk_manifest_path: assets/hi/manifest_hi.json
  manifest_comparison: parsed-JSON-structural-equality
  inline_atlas_path: index.html::ATLAS_HI
  disk_atlas_path: assets/hi/atlas_hi.png
  atlas_comparison: decoded-RGBA-size-and-full-pixel-array
  png_byte_comparison: false
  mismatch_severity: fail

reports:
  verification: tier_a_report.json
  selftest: tier_a_selftest_report.json

negative_selftest:
  required: true
  target_independent: true
  deterministic: true
  in_memory: true
  required_groups:
    - A1-invalid-rectangle
    - A2-out-of-bounds
    - A3-invalid-png
    - A4-overlap
    - A5-missing-required-name
    - A6-hi-only-name
    - A7-manifest-mismatch
    - A8-rgba-or-size-mismatch
    - A9-missing-hero-frame
    - B1-down-visible-face-and-centering
    - B2-up-noface
    - B3-side-visible-face
    - B4-side-right-centroid
    - B5-down-up-relative
```

---

# 19. Change-control boundary

Approval of this document freezes all of the following for Tier A rc2:

* checkpoint tag `tierA-hero-fix-v2`;
* checkpoint SHA `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf`;
* test-harness separation;
* committed-files-only input policy;
* required 34-name list;
* rectangle validity rules;
* half-open overlap rules;
* base and HI containment checks;
* HI subset rule;
* inline/disk HI manifest equality;
* inline/disk HI RGBA equality;
* nine required hero frames in both atlases;
* `alpha > 0` opaque-pixel rule;
* 50% head-region formula;
* `ceil` rounding;
* fixed skin-color mask;
* `T_FACE = 0.08`;
* `T_NOFACE = 0.01`;
* down visible-face requirement;
* down centered-centroid requirement;
* `T_CENTER = 0.05`;
* side visible-face requirement;
* removal of the side upper-face-ratio condition;
* `T_SIDE_RIGHT = 0.57`;
* exclusive side centroid comparison;
* five-times down/up relative condition;
* machine-readable report requirements;
* negative self-test requirements;
* exit-code contract;
* determinism requirements.

This rc2 document explicitly supersedes the rc1 side classifier:

```text
0.01 < side_face_ratio < 0.08
```

and the former side centroid rule:

```text
normalized_skin_centroid_x > 0.50
```

They must not be implemented as active rc2 acceptance rules.

After approval, `tests/tier_a.py` may implement the rc2 rules but must not alter them to fit further observed target measurements.

Any subsequent substantive change requires:

1. a new preregistration revision;
2. a written rationale;
3. explicit approval;
4. a new Tier A version or checkpoint designation when the target or acceptance boundary changes.
