# Application tests

End-to-end tests of the whole app in a real browser, with [Playwright](https://playwright.dev/).

Playwright starts both servers itself, on their own ports so they don't clash with the dev servers:

- **API** on 8001: `backend/tests/e2e_server.py`, using a throwaway Postgres container (with the sample places from `app.seed`) and a FakeLLM instead of a real LLM, so no API calls are made.
- **UI** on 5174: the Vite dev server, pointed at that API.

## Setup

Needs Docker running, plus the backend and frontend set up as in their READMEs.

```sh
cd application-tests
pnpm install
pnpm exec playwright install chromium
```

## Running

```sh
pnpm test          # run headless
pnpm test:ui       # Playwright's UI mode: watch, step through, and re-run tests
pnpm report        # open the report from the last run
```

The first run builds the database image, so it's slower.
