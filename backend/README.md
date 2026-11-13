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

## Database

Postgres runs in Docker (`compose.yaml`), on `localhost:5432` with user, password and database all `aiplayground`.

```sh
docker compose up -d      # start in the background
docker compose down       # stop (data is kept in the db-data volume)
docker compose down -v    # stop and delete all data
docker compose exec db psql -U aiplayground   # open a SQL shell
```

### Migrations

Tables are defined in `src/app/models.py` and migrated with Alembic (`migrations/`).

```sh
uv run alembic upgrade head                                   # apply all migrations (run after setup)
uv run alembic revision --autogenerate -m "describe change"   # after changing models; review the generated file
uv run alembic downgrade -1                                   # undo the last migration
```

## Running

```sh
uv run fastapi dev      # auto-reload, http://127.0.0.1:8000
uv run fastapi run      # no reload
```

API docs are at http://127.0.0.1:8000/docs. The entrypoint (`app.main:app`) is set in `pyproject.toml`, so no path is needed.

## Linting and formatting

[Ruff](https://docs.astral.sh/ruff/) does both; its settings are in `pyproject.toml`.

```sh
uv run ruff check --fix .   # lint, fixing what it safely can
uv run ruff format .        # format
```

## Testing

```sh
uv run pytest
```

Tests need the Docker database running. They use a separate `aiplayground_test` database on the same server, created and reset automatically, so your dev data is never touched.
