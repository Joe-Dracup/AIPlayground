# Backend

FastAPI API for AIPlayground.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (`brew install uv`). It installs Python 3.13 for you if you don't have it.

## Setup from a fresh clone

```sh
cd backend
uv sync                 # create .venv and install dependencies
cp .env.example .env    # then adjust values if needed
```

`.env` is gitignored. `CORS_ORIGINS` is required — the app won't start without it. The default allows the Vite dev server at `http://localhost:5173`.

## Running

```sh
uv run fastapi dev      # auto-reload, http://127.0.0.1:8000
uv run fastapi run      # no reload
```

API docs are at http://127.0.0.1:8000/docs. The entrypoint (`app.main:app`) is set in `pyproject.toml`, so no path is needed.

## Testing

```sh
uv run pytest
```
