"""Модели ValutaTrade Hub: User, Wallet, Portfolio."""
import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError

# Временный кэш курсов — до подключения Parser Service (этап 6–7).
# Позже будет читаться из data/rates.json через SettingsLoader.
_PLACEHOLDER_RATES: dict[str, float] = {
    "EUR_USD": 1.0786,
    "GBP_USD": 1.27,
    "RUB_USD": 0.01016,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "SOL_USD": 145.12,
}


class User:
    """Пользователь системы."""

    def __init__(
            self,
            user_id: int,
            username: str,
            password: str | None = None,
            hashed_password: str | None = None,
            salt: str | None = None,
            registration_date: datetime | None = None,
    ) -> None:
        self._user_id = user_id
        self.username = username
        if hashed_password is not None and salt is not None:
            self._hashed_password = hashed_password
            self._salt = salt
        elif password is not None:
            self._salt = secrets.token_hex(8)
            self._hashed_password = self._hash_password(password)
        else:
            raise ValueError(
                "Укажите либо password, либо пару hashed_password + salt"
            )
        self._registration_date = registration_date or datetime.now()

    # --- свойства ---

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # --- методы ---

    def get_user_info(self) -> dict:
        """Информация о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Меняет пароль пользователя (с новой солью и хешем)."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли пароль с сохранённым хешем."""
        if not isinstance(password, str):
            return False
        return secrets.compare_digest(
            self._hash_password(password), self._hashed_password
        )

    # --- сериализация ---

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

    # --- внутреннее ---

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self._salt).encode("utf-8")).hexdigest()


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = currency_code
        self.balance = balance  # через сеттер — валидация

    @property
    def currency_code(self) -> str:
        return self._currency_code

    @currency_code.setter
    def currency_code(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = value.upper().strip()
        if not (2 <= len(code) <= 5) or " " in code:
            raise ValueError(f"Некорректный код валюты: '{value}'")
        self._currency_code = code

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    # --- операции ---

    def deposit(self, amount: float) -> None:
        """Пополняет баланс на amount (>0)."""
        self._validate_amount(amount, "пополнения")
        self.balance = self._balance + amount

    def withdraw(self, amount: float) -> None:
        """Снимает amount (>0), если хватает средств."""
        self._validate_amount(amount, "снятия")
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self._currency_code)
        self.balance = self._balance - amount

    def get_balance_info(self) -> str:
        return f"{self._currency_code}: {self._balance:.4f}"

    # --- сериализация ---

    def to_dict(self) -> dict:
        return {"currency_code": self._currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        return cls(currency_code=data["currency_code"], balance=data["balance"])

    # --- внутреннее ---

    @staticmethod
    def _validate_amount(amount: float, action: str) -> None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError(f"Сумма {action} должна быть числом")
        if amount <= 0:
            raise ValueError(f"Сумма {action} должна быть положительной")


class Portfolio:
    """Набор кошельков пользователя."""

    def __init__(self, user: User, wallets: dict[str, Wallet] | None = None) -> None:
        self._user = user
        self._user_id = user.user_id
        self._wallets: dict[str, Wallet] = dict(wallets) if wallets else {}

    # --- свойства ---

    @property
    def user(self) -> User:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков (защита от внешних изменений)."""
        return dict(self._wallets)

    # --- операции ---

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет кошелёк, если его ещё нет. Возвращает объект Wallet."""
        code = currency_code.upper().strip()
        if code in self._wallets:
            return self._wallets[code]
        get_currency(code)  # бросит CurrencyNotFoundError, если код неизвестен
        self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        return self._wallets.get(currency_code.upper().strip())

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Суммарная стоимость портфеля в base_currency."""
        base = base_currency.upper().strip()
        get_currency(base)  # CurrencyNotFoundError, если база неизвестна
        total = 0.0
        for code, wallet in self._wallets.items():
            total += wallet.balance * self._rate_to_base(code, base)
        return round(total, 2)

    # --- сериализация ---

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, user: User) -> "Portfolio":
        wallets = {
            code: Wallet.from_dict(w)
            for code, w in data.get("wallets", {}).items()
        }
        return cls(user=user, wallets=wallets)

    # --- внутреннее ---

    @staticmethod
    def _rate_to_base(code: str, base: str) -> float:
        if code == base:
            return 1.0
        direct = f"{code}_{base}"
        if direct in _PLACEHOLDER_RATES:
            return _PLACEHOLDER_RATES[direct]
        reverse = f"{base}_{code}"
        if reverse in _PLACEHOLDER_RATES:
            return 1.0 / _PLACEHOLDER_RATES[reverse]
        return 0.0  # курс неизвестен — вклад не учитываем