"""Хранилище курсов: снимок rates.json + история exchange_rates.json."""
from datetime import UTC, datetime

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Сохраняет свежие курсы в снимок и в историю."""

    def __init__(
            self,
            config: ParserConfig | None = None,
            db: DatabaseManager | None = None,
    ) -> None:
        self.config = config or ParserConfig()
        self.db = db or DatabaseManager()

    def save(self, rates: dict[str, float], sources: dict[str, str]) -> dict:

        now = datetime.now(UTC).replace(microsecond=0)
        now_iso = now.isoformat().replace("+00:00", "Z")

        # 1) Обновляем снимок rates.json
        snapshot = self._build_snapshot(rates, sources, now_iso)
        self.db.write_json(self.config.RATES_FILE_PATH, snapshot)

        # 2) Дописываем историю exchange_rates.json
        history_added = self._append_history(rates, sources, now_iso)

        return {
            "saved": len(rates),
            "history_added": history_added,
            "last_refresh": now_iso,
        }

    # --- внутреннее ---

    def _build_snapshot(
            self, rates: dict[str, float], sources: dict[str, str], now_iso: str
    ) -> dict:
        current = self.db.read_json(
            self.config.RATES_FILE_PATH, default={"pairs": {}}
        )
        pairs = current.get("pairs", {})

        for key, rate in rates.items():
            new_updated = now_iso
            existing = pairs.get(key)
            if existing and existing.get("updated_at", "") > new_updated:
                continue  # старая запись свежее — не перезаписываем
            pairs[key] = {
                "rate": rate,
                "updated_at": new_updated,
                "source": sources.get(key, "unknown"),
            }

        return {"pairs": pairs, "last_refresh": now_iso}

    def _append_history(
            self, rates: dict[str, float], sources: dict[str, str], now_iso: str
    ) -> int:
        history = self.db.read_json(self.config.HISTORY_FILE_PATH, default=[])
        if not isinstance(history, list):
            history = []

        existing_ids = {entry.get("id") for entry in history}
        added = 0

        for key, rate in rates.items():
            try:
                from_code, to_code = key.split("_", 1)
            except ValueError:
                continue
            entry_id = f"{from_code}_{to_code}_{now_iso}"
            if entry_id in existing_ids:
                continue
            history.append(
                {
                    "id": entry_id,
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": rate,
                    "timestamp": now_iso,
                    "source": sources.get(key, "unknown"),
                }
            )
            added += 1

        if added:
            self.db.write_json(self.config.HISTORY_FILE_PATH, history)
        return added