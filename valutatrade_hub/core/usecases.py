"""Бизнес-логика ValutaTrade Hub."""

from datetime import UTC, datetime, timedelta

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    validate_amount,
    validate_currency_code,
    validate_password,
    validate_username,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

_db = DatabaseManager()
_settings = SettingsLoader()

# Начальные курсы (bootstrap rates.json при первом запуске)
_DEFAULT_RATES: dict[str, dict] = {
    "EUR_USD": {"rate": 1.0786, "source": "bootstrap"},
    "GBP_USD": {"rate": 1.2700, "source": "bootstrap"},
    "RUB_USD": {"rate": 0.01016, "source": "bootstrap"},
    "BTC_USD": {"rate": 59337.21, "source": "bootstrap"},
    "ETH_USD": {"rate": 3720.00, "source": "bootstrap"},
    "SOL_USD": {"rate": 145.12, "source": "bootstrap"},
}


# ---------- низкоуровневое хранилище ----------


def _load_users() -> list[dict]:
    return _db.read_json(_db.users_path, default=[])


def _save_users(users: list[dict]) -> None:
    _db.write_json(_db.users_path, users)


def _load_portfolios() -> list[dict]:
    return _db.read_json(_db.portfolios_path, default=[])


def _save_portfolios(portfolios: list[dict]) -> None:
    _db.write_json(_db.portfolios_path, portfolios)


def _next_user_id(users: list[dict]) -> int:
    return max((u["user_id"] for u in users), default=0) + 1


def _find_user_data(username: str) -> dict | None:
    for u in _load_users():
        if u["username"] == username:
            return u
    return None


def _find_user_by_id(user_id: int) -> User | None:
    for u in _load_users():
        if u["user_id"] == user_id:
            return User.from_dict(u)
    return None


def _get_portfolio(user: User) -> Portfolio:
    for p in _load_portfolios():
        if p["user_id"] == user.user_id:
            return Portfolio.from_dict(p, user)
    return Portfolio(user)


def _save_portfolio(portfolio: Portfolio) -> None:
    portfolios = _load_portfolios()
    for i, p in enumerate(portfolios):
        if p["user_id"] == portfolio.user_id:
            portfolios[i] = portfolio.to_dict()
            break
    else:
        portfolios.append(portfolio.to_dict())
    _save_portfolios(portfolios)


# ---------- курсы (кэш rates.json) ----------


def _bootstrap_rates_if_missing() -> None:
    """Создаёт rates.json с заглушками, если файла ещё нет."""
    if _db.rates_path.exists():
        return
    now = datetime.now(UTC).isoformat(timespec="seconds")
    pairs = {k: {**v, "updated_at": now} for k, v in _DEFAULT_RATES.items()}
    _db.write_json(_db.rates_path, {"pairs": pairs, "last_refresh": now})


def _is_fresh(updated_at: str | None) -> bool:
    if not updated_at:
        return False
    ttl = _settings.get("rates_ttl_seconds", 300)
    try:
        dt = datetime.fromisoformat(updated_at)
    except ValueError:
        return False
    return datetime.now(UTC) - dt < timedelta(seconds=ttl)


def get_rate(from_code: str, to_code: str) -> dict:
    """Возвращает курс from→to из локального кэша rates.json.

    :raises CurrencyNotFoundError: неизвестный код валюты.
    :raises ApiRequestError: курс недоступен в кэше.
    """
    _bootstrap_rates_if_missing()
    f = validate_currency_code(from_code)
    t = validate_currency_code(to_code)
    get_currency(f)
    get_currency(t)

    if f == t:
        return {
            "from": f,
            "to": t,
            "rate": 1.0,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "stale": False,
        }

    cache = _db.read_json(_db.rates_path, default={"pairs": {}})
    pairs = cache.get("pairs", {})

    for key, invert in ((f"{f}_{t}", False), (f"{t}_{f}", True)):
        if key in pairs:
            info = pairs[key]
            rate = 1.0 / info["rate"] if invert else info["rate"]
            updated_at = info.get("updated_at")
            return {
                "from": f,
                "to": t,
                "rate": rate,
                "updated_at": updated_at,
                "stale": not _is_fresh(updated_at),
            }

    raise ApiRequestError(f"Курс {f}→{t} недоступен. Повторите попытку позже.")


# ---------- usecases ----------


@log_action("REGISTER")
def register(username: str, password: str) -> User:
    """Регистрирует нового пользователя и создаёт пустой портфель."""
    username = validate_username(username)
    password = validate_password(password)
    if _find_user_data(username):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    users = _load_users()
    user = User(user_id=_next_user_id(users), username=username, password=password)
    users.append(user.to_dict())
    _save_users(users)
    _save_portfolio(Portfolio(user))
    return user


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    """Проверяет логин/пароль, возвращает User."""
    data = _find_user_data(validate_username(username))
    if not data:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = User.from_dict(data)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


@log_action("BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float) -> dict:
    """Покупает amount единиц валюты, создавая кошелёк при необходимости."""
    user = _find_user_by_id(user_id)
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден")

    code = validate_currency_code(currency_code)
    get_currency(code)
    amt = validate_amount(amount)

    portfolio = _get_portfolio(user)
    wallet = portfolio.get_wallet(code)
    before = wallet.balance if wallet else 0.0
    if wallet is None:
        wallet = portfolio.add_currency(code)

    wallet.deposit(amt)
    after = wallet.balance
    _save_portfolio(portfolio)

    try:
        rate_info = get_rate(code, "USD")
        rate = rate_info["rate"]
        cost_usd = amt * rate
    except ApiRequestError:
        rate, cost_usd = None, None

    return {
        "code": code,
        "amount": amt,
        "before": before,
        "after": after,
        "rate": rate,
        "cost_usd": cost_usd,
    }


@log_action("SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float) -> dict:
    """Продаёт amount единиц валюты с кошелька пользователя."""
    user = _find_user_by_id(user_id)
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден")

    code = validate_currency_code(currency_code)
    get_currency(code)
    amt = validate_amount(amount)

    portfolio = _get_portfolio(user)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise CurrencyNotFoundError(code)
    if wallet.balance < amt:
        raise InsufficientFundsError(wallet.balance, amt, code)

    before = wallet.balance
    wallet.withdraw(amt)
    after = wallet.balance
    _save_portfolio(portfolio)

    try:
        rate_info = get_rate(code, "USD")
        rate = rate_info["rate"]
        revenue_usd = amt * rate
    except ApiRequestError:
        rate, revenue_usd = None, None

    return {
        "code": code,
        "amount": amt,
        "before": before,
        "after": after,
        "rate": rate,
        "revenue_usd": revenue_usd,
    }


def show_portfolio(user_id: int, base_currency: str = "USD") -> dict:
    """Собирает данные о портфеле для отображения."""
    user = _find_user_by_id(user_id)
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден")

    base = validate_currency_code(base_currency)
    get_currency(base)

    portfolio = _get_portfolio(user)
    rows = []
    total = 0.0

    for code, wallet in portfolio.wallets.items():
        if code == base:
            rate = 1.0
        else:
            try:
                rate = get_rate(code, base)["rate"]
            except ApiRequestError:
                rate = 0.0
        value = wallet.balance * rate
        total += value
        rows.append(
            {"currency": code, "balance": wallet.balance, "value": round(value, 2)}
        )

    return {
        "username": user.username,
        "base": base,
        "rows": rows,
        "total": round(total, 2),
    }
