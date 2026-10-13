"""Координация обновления курсов из нескольких источников."""
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = get_logger()


class RatesUpdater:
    """Опрашивает всех клиентов, объединяет и сохраняет курсы."""

    def __init__(
            self,
            clients: list[BaseApiClient] | None = None,
            storage: RatesStorage | None = None,
    ) -> None:
        config = ParserConfig()
        self.clients = clients or [
            CoinGeckoClient(config),
            ExchangeRateApiClient(config),
        ]
        self.storage = storage or RatesStorage(config)

    def run_update(self, source: str | None = None) -> dict:

        logger.info("Starting rates update...")
        rates: dict[str, float] = {}
        sources: dict[str, str] = {}
        errors: list[dict] = []

        for client in self.clients:
            if source and source.lower() not in client.source.lower():
                continue
            logger.info("Fetching from %s...", client.source)
            try:
                client_rates = client.fetch_rates()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to fetch from %s: %s", client.source, exc)
                errors.append({"source": client.source, "error": str(exc)})
                continue
            rates.update(client_rates)
            for key in client_rates:
                sources[key] = client.source
            logger.info("Fetching from %s... OK (%d rates)", client.source, len(client_rates))

        if not rates:
            logger.error("No rates fetched from any source")
            return {"rates": {}, "sources": {}, "errors": errors}

        summary = self.storage.save(rates, sources)
        logger.info(
            "Saved %d rates, %d history entries, last_refresh=%s",
            summary["saved"],
            summary["history_added"],
            summary["last_refresh"],
        )
        return {"rates": rates, "sources": sources, "errors": errors, **summary}