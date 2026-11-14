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
docker compose up -d --build   # rebuild after changing db/Dockerfile
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

### Sample data

```sh
uv run python -m app.seed   # add (or reset) sample places around Manchester city centre
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

Tests need Docker running, but not the dev database. They start their own throwaway Postgres container ([Testcontainers](https://testcontainers.com/)), built from `db/Dockerfile` and set up by running the migrations, and delete it when they finish. The first run builds the image, so it's slower.
