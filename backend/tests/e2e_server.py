"""Runs the API for the application tests (/application-tests), on a throwaway database with the
sample places, and with a FakeLLM instead of a real LLM. Needs Docker.

    uv run python tests/e2e_server.py

Listens on PORT (default 8001). The database is deleted when the server stops.
"""

import asyncio
import os
import signal

import uvicorn
from containers import test_database


def main() -> None:
    with test_database() as url:
        os.environ["DATABASE_URL"] = url

        # Imported only now, because the app reads DATABASE_URL when it's first imported.
        from app import seed
        from app.llm import FAKE_REPLIES, FakeLLM, get_llm
        from app.main import app

        asyncio.run(seed.main())

        app.dependency_overrides[get_llm] = lambda: FakeLLM(replies=FAKE_REPLIES)

        uvicorn.run(
            app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), log_level="warning"
        )
        # Playwright stops this with SIGINT to the whole process group, and `uv run` forwards its
        # copy a moment later. Ignore it, so it can't interrupt deleting the database container.
        signal.signal(signal.SIGINT, signal.SIG_IGN)


if __name__ == "__main__":
    main()
