"""Singleton-конфигурация ValutaTrade Hub."""
import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "logs_dir": "logs",
    "log_file": "logs/actions.log",
    "log_format": "text",  # "text" или "json"
    "log_level": "INFO",
    "rates_ttl_seconds": 300,  # 5 минут
    "base_currency": "USD",
}


class SettingsLoader:

    _instance: "SettingsLoader | None" = None

    def __new__(cls, config_path: str | Path | None = None) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str | Path | None = None) -> None:
        if self._initialized:
            return
        self._config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self._config_path = Path(config_path) if config_path else None
        self._load_from_file()
        self._initialized = True

    def _load_from_file(self) -> None:
        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    user_config = json.load(f)
                if isinstance(user_config, dict):
                    self._config.update(user_config)
            except (OSError, json.JSONDecodeError):
                # Битый конфиг — остаёмся на дефолтах, не падаем
                pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def reload(self) -> None:
        """Перечитывает конфиг с диска."""
        self._config = dict(DEFAULT_CONFIG)
        self._load_from_file()

    @classmethod
    def _reset(cls) -> None:
        """Только для тестов: сбрасывает singleton."""
        cls._instance = None

    def __repr__(self) -> str:
        return f"SettingsLoader(config_keys={list(self._config.keys())})"