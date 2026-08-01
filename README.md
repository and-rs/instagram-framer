# Instagram Framer

FastAPI + HTMX app for preparing artwork posts for Instagram.

## Local usage

```bash
just start
```

Open:

```text
http://127.0.0.1:8000
```

## Flow

1. Upload artwork images.
2. Enter technique/material and dimensions.
3. Generate `2000x2000` square images and a Spanish caption.
4. Review the generated images and caption.
5. Download the ZIP.

## Environment variables

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
FRAME_BACKGROUND=#f7f3ea
FRAME_SHADOW_OPACITY=0.22
MAX_UPLOAD_COUNT=10
MAX_UPLOAD_MB=50
MAX_OUTPUT_MB=8
GENERATED_TTL_SECONDS=3600
```

## Commands

```bash
just start
just test
just check
```

## TODO

### Foundation

- [ ] Accept standard image formats and Nikon `.NEF` RAW files.
- [ ] Decode uploads, apply EXIF orientation, and create a normalized working image.
- [ ] Let the user select the Scene, Detail, or Documentation recipe before processing.
- [ ] Improve job persistence if the app is used with multiple instances or restarts.

### Automated detection

- [ ] Detect the painting and estimate its bounds.
- [ ] Detect four painting corners for the Documentation recipe.
- [ ] Measure detection confidence and clearly surface failures.
- [ ] Automate Scene cropping around the painting and intentional environment.

### Image adjustments

- [ ] Define a reliable adjustment pipeline for white balance, exposure, lighting, and color.
- [ ] Evaluate a vision model that returns structured adjustment values for the tuning tools; it must not generate or alter image content.
- [ ] Ensure adjustments preserve the painting's visual fidelity.

### Scene recipe

- [ ] Detect the painting and correct rotation only when needed.
- [ ] Produce a balanced, full-bleed 1:1 crop with the painting and its environment.
- [ ] Do not apply framing.

### Detail recipe

- [ ] Preserve the full horizontal detail image without cropping.
- [ ] Tune the image and apply the existing square framing treatment.

### Documentation recipe

- [ ] Detect painting corners, correct perspective, and crop to the exact painting bounds.
- [ ] Apply image adjustments.
- [ ] Always apply the existing square framing treatment for a consistent 1:1 output.

### Later

- [ ] Add optional reference-style matching.
- [ ] Add manual crop and corner-adjustment tools where automation is insufficient.
- [ ] Add manual caption editing before downloading.
- [ ] Revisit carousel ordering UX later.
- [ ] Restore Instagram publishing once the image-preparation workflow is established.
