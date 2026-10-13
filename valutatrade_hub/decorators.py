"""Декораторы ValutaTrade Hub."""

import functools
from collections.abc import Callable
from typing import Any

from valutatrade_hub.logging_config import get_logger

logger = get_logger()


def log_action(action: str, verbose: bool = False) -> Callable:
    """Декоратор для логирования доменных операций."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            base = action
            if verbose:
                base += f" args={args[1:]} kwargs={kwargs}"
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    "%s result=ERROR error_type=%s error_message=%s",
                    base,
                    type(exc).__name__,
                    exc,
                )
                raise
            else:
                logger.info("%s result=OK", base)
                return result

        return wrapper

    return decorator
