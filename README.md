# Framer

Framer prepares finished artwork photographs for social posts and future sales channels.

## QOL todos

- [ ] Merge the nix files into only shell.nix.
- [ ] Preserve state even after reload.
- [ ] Think of way to insert a small flow before processing the framing, in which the user can select one of the uploaded photos and apply some edits with a common set of sliders, and then frame the edited one instead of the original.
- [ ] Setup proper project formatting with reasonable TBD JS, HTML, CSS, Python and Jinja tooling.
  - [ ] Should happen on precommit and there need to be automated scripts to do so.
- [ ] Rethink the need for JS files and if can we use a more structured library that would fit the use case better.
- [ ] For some reason the CSS file has a bunch or redefined css classes from Tailwind, it should be compact, follow a shadcn example, and stardadize colors, ratios and styles, not redefined library baselines.
- [ ] We should have a regular global.css file that can be user modified, and then a different minified output.css that actually gets loaded by FastAPI/HTMX.

## Current Workflow

1. Photograph and edit the artwork into its desired scenarios outside Framer.
2. Upload the prepared images to Framer and select one reference image.
3. Enter the artwork number, material, dimensions, and collection information.
4. Generate framed `2000x2000` JPEGs, an artwork description, and a Spanish caption.
5. Review and download the post-ready assets.

Non-square images receive the framing treatment; square images are exported full bleed.

## Scope

Framer is a final QA and publishing-preparation tool. It does not perform RAW development, automatic scene composition, crop automation, perspective correction, or model-driven image edits.

The intended wider workflow is:

`create painting -> photograph painting -> edit into scenarios -> Framer QA/frame/caption -> Instagram and ecommerce`

## Product Roadmap

- [ ] Design per-image optional QA adjustments before framing: exposure, temperature, contrast, highlights, shadows, and vibrance.
- [ ] Preserve durable artwork records, source photographs, scenario edits, Framer exports, captions, and adjustment history.
- [ ] Create ecommerce product records from archived artwork data.
- [ ] Add an approval queue and later scheduled Instagram publishing.

## Development

Dependencies are managed with `uv` through `pyproject.toml` and `uv.lock`.

```bash
uv sync
just start
```

Open <http://127.0.0.1:8000>.

```bash
just start
just test
just check
just css
just css-watch
```

`just css` builds `static/styles.css` from `static/tailwind.css`. Nix is required only to rebuild styles.

Environment variable examples are in `.env.example`.
