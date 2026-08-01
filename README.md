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

- [ ] Improve job persistence if the app is used with multiple instances or restarts.
- [ ] Add manual caption editing before downloading.
- [ ] Revisit carousel ordering UX later.
