"""Singleton-абстракция над JSON-хранилищем."""
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader

_UNSET = object()


class DatabaseManager:
    """Singleton для чтения/записи JSON-файлов."""

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
        return cls._instance

    def __init__(self) -> None:
        """Ничего не делает: singleton-паттерн."""

    def read_json(self, path: str | Path, default: Any = _UNSET) -> Any:
        """Читает JSON-файл.

        Если default не передан — возвращает [] для отсутствующего/битого файла.
        Если default передан явно (в т.ч. None) — возвращает его.
        """
        p = Path(path)
        fallback = [] if default is _UNSET else default
        if not p.exists():
            return fallback
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return fallback

    def write_json(self, path: str | Path, data: Any) -> None:
        """Атомарно пишет JSON-файл: tmp → rename."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(p.parent), prefix=p.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, p)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @property
    def users_path(self) -> Path:
        return Path(self._settings.get("users_file"))

    @property
    def portfolios_path(self) -> Path:
        return Path(self._settings.get("portfolios_file"))

    @property
    def rates_path(self) -> Path:
        return Path(self._settings.get("rates_file"))

    @property
    def history_path(self) -> Path:
        return Path(self._settings.get("history_file"))

    @classmethod
    def _reset(cls) -> None:
        """Только для тестов: сбрасывает singleton."""
        cls._instance = None