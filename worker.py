"""Standalone background worker entrypoint for durable queued ingestion."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

import background_jobs

load_dotenv(Path(__file__).parent / ".env", override=False)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    background_jobs.run_worker_forever()


if __name__ == "__main__":
    main()
