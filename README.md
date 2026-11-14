# AIPlayground

A playground for me to learn Python, and general AI tooling concepts.

| Folder | What's in it |
|---|---|
| `backend/` | FastAPI API, Postgres + PostGIS, Alembic migrations, pytest tests |
| `frontend/` | Vue 3 chat UI |
| `application-tests/` | Playwright tests of the whole app in a browser |

Each folder's README has its setup and run commands.

## Key decisions

**Tooling.** [uv](https://docs.astral.sh/uv/) manages Python, the virtualenv and locked dependencies. Ruff does linting and formatting, on save in VS Code.

**Injected LLM clients.** Anthropic's API is used at the moment, but loosely coupled to the chat part of the app: the rest of the app only depends on `LLMClient`. Messages are stored in our own provider-neutral format (`app/llm/messages.py`): text, tool calls, tool results, reasoning, and a catch-all for provider-only content. Adding another provider means a client that translates to and from it. Also built a `FakeLLM` with pre-defined responses for testing purposes.

**Didn't use the SDK's tool runner.** For the reasons above - Anthropic's SDK could drive the chat part of the app, but writing our own chat handling (`chat.py`) allows us to swap to `FakeLLM` or another provider without worrying about this breaking. It also means `FakeLLM` can drive the whole loop in tests, and every step (tool calls and results) gets saved to the database.

Tools are registered centrally to allow for easily adding new ones, this is the interesting bit of all of this so adding new tools should be as easy as adding a file and registering it

**Conversations in Postgres, content as `jsonb`.** Each message's parts are stored as `jsonb`, along with the provider and model that wrote it and the provider's raw response. Provider-only content (e.g. thinking signatures) is kept exactly as received, because it has to be sent back unchanged on later turns. SQLAlchemy 2 (async) is the ORM; Alembic handles migrations.

**Our own database image.** `backend/db/Dockerfile` is the official `postgres:18` image plus PostGIS, rather than a ready-made PostGIS image, so more extensions (e.g. pgvector) can be added to the same image later. Dev (Compose) and tests (Testcontainers) both build from it. Extensions are switched on by hand-written migrations.

**PostGIS for places.** One `places` table:
- `location` is `geography(Point, 4326)`, so distances come out in metres
- `tags` is a `text[]` with a GIN index, for "has all these tags" searches
- `category` and `tags` come from a fixed vocabulary, which reaches the LLM as enums

GeoAlchemy2 provides the column types and lets Alembic autogenerate spatial indexes. The LLM searches with two tools: `find_place` (name → id), then `search_places` (within a distance of that place, by category and tags). Sample data comes from a seed script (`python -m app.seed`) until there's an import job.

**One place to get database sessions.** Everything that uses the database (the conversation store, the place tools) gets sessions through `get_sessions`, so tests override that once.

**Tests on a real database.** Backend tests run against a throwaway Postgres from Testcontainers, with the schema built by running the migrations. There's no SQLite or in-memory stand-in, because `jsonb` and PostGIS behaviour is what's being tested. The Playwright tests start their own API (`backend/tests/e2e_server.py`: container, migrations, seed data and `FakeLLM`) and Vite dev server, on separate ports from dev.

## Things to follow up on

- Proper search for place in tooling - not just name contains
- Import data for places properly including looking at images and tagging based on that
- Softer text for vibe rather than just places - e.g. cozy inn, might be a nice place to sit by a wood fire
- Search places based on polygons - walkable distance in time from a location - look at how long that would take long maps then do postGIS search in that polygon
- Think about caching, how can i cache places that are regularly accessed - feels like it could be tricky with all the search being done at the db level atm?
