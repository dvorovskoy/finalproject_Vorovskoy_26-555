"""Простейший планировщик периодического обновления курсов."""

import time
from collections.abc import Callable

from valutatrade_hub.logging_config import get_logger

logger = get_logger()


def run_periodically(
    task: Callable[[], None],
    interval_seconds: int = 3600,
    max_runs: int | None = None,
) -> None:

    runs = 0
    while True:
        logger.info("Scheduler: running task (run #%d)", runs + 1)
        try:
            task()
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduler: task failed: %s", exc)

        runs += 1
        if max_runs is not None and runs >= max_runs:
            logger.info("Scheduler: max_runs reached (%d), stopping", max_runs)
            return
        logger.info("Scheduler: sleeping %d seconds", interval_seconds)
        time.sleep(interval_seconds)
