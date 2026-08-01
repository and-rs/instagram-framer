start:
    uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

css:
    nix-shell --pure --run 'tailwindcss -i static/tailwind.css -o static/styles.css --minify'

css-watch:
    nix-shell --pure --run 'tailwindcss -i static/tailwind.css -o static/styles.css --watch'

test:
    uv run pytest

check:
    uv run pytest
    uv run python -m compileall app tests
