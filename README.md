# Framer

FastAPI + HTMX app for preparing artwork images for Instagram.

## Current status

### Framing workflow: working

1. Upload one or more standard artwork images.
2. Enter the technique/material and dimensions.
3. Generate `2000x2000` JPEGs and a Spanish caption.
4. Review the images and caption, then download a ZIP.

Non-square images receive the existing framing treatment; square images are exported full bleed. This remains the active production workflow while Scene is built separately.

### Scene workflow: planned

`/scene` currently documents the recipe only. It does not accept or process uploads yet.

The first Scene release produces a balanced, full-bleed `2000x2000` crop of an artwork in its environment. It preserves meaningful supporting objects and intentional negative space rather than isolating or centering the painting.

## Development setup

Python dependencies are managed exclusively with `uv` through `pyproject.toml` and `uv.lock`.

```bash
uv sync
just start
```

Open <http://127.0.0.1:8000>.

`requirements.txt` is intentionally not used.

## Commands

```bash
just start
just test
just check
just css
just css-watch
```

`just css` builds the committed `static/styles.css` from `static/tailwind.css`. It uses Tailwind CSS v4's pinned standalone CLI through `shell.nix`; Nix is required only to rebuild styles, not to run the application.

## Environment variables

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
FRAME_BACKGROUND=#f7f3ea
FRAME_SHADOW_OPACITY=0.22
MAX_UPLOAD_COUNT=10
MAX_UPLOAD_MB=50
MAX_OUTPUT_MB=8
GENERATED_TTL_SECONDS=3600
```

The frame settings belong to the active framing workflow. Scene-specific settings will be introduced alongside their implementation rather than documented in advance.

## Scene implementation record

| Stage | Status | Evidence required before enabling |
| --- | --- | --- |
| Decode and normalize | Planned | Raster and NEF fixtures, EXIF-orientation tests, invalid-upload handling |
| Composition analysis | Planned | Structured response validation, positive/negative scene fixtures, confidence and failure reporting |
| Full-resolution crop | Planned | Approved 1:1 fixture crops that retain the artwork, context, and negative space |
| Color and lighting | Planned | Bounded adjustment tests, before/after review, recorded applied values |
| Export and audit | Planned | `2000x2000` output assertions and per-job analysis/transform manifest |
| Straightening | Deferred | Separate evaluation showing rotation improves Scene images without harming composition |

An implemented stage is not considered working because code exists alone. It must have the listed test evidence, user-visible behavior, and a recorded limitation or failure path.

## Scene subplan

### 1. Decode and normalize

- Accept standard raster images and Nikon `.NEF` RAW files.
- Apply EXIF orientation and create a full-resolution normalized working image.
- For NEF, decode locally before analysis. Create a downscaled JPEG analysis preview, but retain the full-resolution decoded image for final processing.
- Store input type, decoder, dimensions, and normalization result in the Scene job manifest.

Why: OpenAI vision analysis consumes a rendered image preview, not raw NEF bytes. Local decoding keeps the final crop and adjustments at full resolution.

### 2. Structured composition analysis

- Send the downscaled preview to the existing OpenAI integration with Structured Outputs.
- Request primary artwork bounds, supporting subjects, intentional negative space, a proposed square crop, confidence, diagnostics, and bounded color/lighting values.
- Validate every coordinate and value deterministically before processing.
- Return an explicit low-confidence or ambiguous result rather than choosing a crop silently.

Why: the desired result is editorial composition, not rectangle detection. The painting, easel, vase, table, and empty wall may all be intentional. The model proposes structured coordinates and values only; it never generates or edits image content.

### 3. Full-resolution 1:1 composition

- Apply the validated square crop to the full-resolution normalized image.
- Preserve the primary artwork while allowing off-center placement, supporting objects, and meaningful negative space.
- Produce a preview before export.
- Do not call the framing pipeline or add a frame/shadow.

Why: a centered crop around detected artwork would destroy the intended composition. Applying the crop at full resolution avoids quality loss from the analysis preview.

### 4. Color and lighting adjustments

- Apply deterministic, conservative full-resolution white balance, exposure, tone, and color adjustments from the validated structured response.
- Use RAW white balance during NEF development where possible; use bounded RGB/tone adjustments for raster inputs.
- Save the exact applied values and show unadjusted and adjusted previews.

Why: the model provides aesthetic guidance, while deterministic bounded transforms preserve fidelity and make every output auditable. No adjustment may generate, remove, or invent image content.

### 5. Export and audit record

- Export an optimized `2000x2000` full-bleed JPEG.
- Store the structured response, validation outcome, crop coordinates in normalized-source pixels, applied adjustments, model/version, and failure reason in a per-job manifest.

Why: Scene automation will sometimes be wrong. An audit record makes results reproducible, debuggable, and safe to revise without losing context.

## Deferred work

- Automatic straightening. It is not needed for the initial Scene composition target and can introduce unnecessary resampling.
- Manual crop and corner-adjustment tools.
- Detail and Documentation recipes.
- Perspective correction. This is Documentation-only because Scene should preserve its photographed environment.
- Multi-instance job persistence.
- Instagram publishing.
