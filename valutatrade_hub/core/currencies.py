"""Иерархия валют и реестр для ValutaTrade Hub."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактная валюта: имя и код с валидацией."""

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя валюты не может быть пустым")
        self._name = value

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError("Код валюты должен быть строкой")
        code = value.upper().strip()
        if not (2 <= len(code) <= 5) or " " in code:
            raise ValueError(f"Некорректный код валюты: '{value}'")
        self._code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для UI и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта (эмитируется государством/зоной)."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта (алгоритм + рыночная капитализация)."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap})"
        )


# Реестр известных валют (можно расширять)
_CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof-of-History", 6.8e10),
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту по коду.

    :raises CurrencyNotFoundError: если код неизвестен или невалиден.
    """
    if not isinstance(code, str):
        raise CurrencyNotFoundError(str(code))
    normalized = code.upper().strip()
    if normalized not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(normalized)
    return _CURRENCY_REGISTRY[normalized]
