"""Клиенты для внешних API: CoinGecko (crypto) и ExchangeRate-API (fiat)."""

from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Абстрактный клиент: возвращает словарь {<FROM>_<TO>: rate}."""

    source: str = "unknown"

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает курсы в формате {'BTC_USD': 59337.21, ...}."""


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для криптовалют."""

    source = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        codes = self.config.CRYPTO_CURRENCIES
        ids = ",".join(self.config.CRYPTO_ID_MAP[c] for c in codes)
        base = self.config.BASE_CURRENCY.lower()
        params = {"ids": ids, "vs_currencies": base}

        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"CoinGecko: network error — {exc}") from exc

        if response.status_code == 429:
            raise ApiRequestError("CoinGecko: превышен лимит запросов (429)")
        if response.status_code != 200:
            raise ApiRequestError(f"CoinGecko: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiRequestError("CoinGecko: некорректный JSON") from exc

        rates: dict[str, float] = {}
        for code in codes:
            coin_id = self.config.CRYPTO_ID_MAP[code]
            entry = data.get(coin_id)
            if isinstance(entry, dict) and base in entry:
                rate = entry[base]
                if isinstance(rate, (int, float)):
                    rates[f"{code}_{self.config.BASE_CURRENCY}"] = float(rate)
        if not rates:
            raise ApiRequestError("CoinGecko: пустой ответ")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для фиатных валют."""

    source = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "ExchangeRate-API: ключ не задан (EXCHANGERATE_API_KEY)"
            )

        base = self.config.BASE_CURRENCY
        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{base}"
        )

        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"ExchangeRate-API: network error — {exc}") from exc

        if response.status_code == 401:
            raise ApiRequestError("ExchangeRate-API: неверный API-ключ (401)")
        if response.status_code == 429:
            raise ApiRequestError("ExchangeRate-API: превышен лимит (429)")
        if response.status_code != 200:
            raise ApiRequestError(f"ExchangeRate-API: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiRequestError("ExchangeRate-API: некорректный JSON") from exc

        if data.get("result") != "success":
            reason = data.get("error-type", "unknown error")
            raise ApiRequestError(f"ExchangeRate-API: {reason}")

        all_rates = data.get("conversion_rates") or data.get("rates") or {}
        rates: dict[str, float] = {}
        for code in self.config.FIAT_CURRENCIES:
            rate = all_rates.get(code)
            if isinstance(rate, (int, float)) and rate > 0:
                # ExchangeRate отдаёт "1 BASE = rate CODE". Нам нужно
                # "1 CODE = ? BASE", поэтому инвертируем.
                rates[f"{code}_{base}"] = 1.0 / float(rate)
        if not rates:
            raise ApiRequestError("ExchangeRate-API: пустой ответ")
        return rates
