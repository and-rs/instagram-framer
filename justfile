start:
    uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
    uv run pytest

check:
    uv run pytest
    uv run python -m compileall app tests
