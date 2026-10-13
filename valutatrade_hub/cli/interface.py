"""CLI ValutaTrade Hub: команды и REPL."""

import shlex

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.updater import RatesUpdater


class Session:
    """Хранит состояние текущей сессии (залогиненный пользователь)."""

    def __init__(self) -> None:
        self.user = None

    @property
    def is_logged_in(self) -> bool:
        return self.user is not None

    def login(self, user) -> None:
        self.user = user

    def logout(self) -> None:
        self.user = None


_session = Session()
_db = DatabaseManager()


# ---------- команды ----------


def cmd_register(args: dict) -> None:
    username = args.get("username")
    password = args.get("password")
    if not username or not password:
        print("Использование: register --username <name> --password <pass>")
        return
    try:
        user = usecases.register(username, password)
    except ValueError as exc:
        print(exc)
        return
    print(
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def cmd_login(args: dict) -> None:
    username = args.get("username")
    password = args.get("password")
    if not username or not password:
        print("Использование: login --username <name> --password <pass>")
        return
    try:
        user = usecases.login(username, password)
    except ValueError as exc:
        print(exc)
        return
    _session.login(user)
    print(f"Вы вошли как '{user.username}'")


def cmd_show_portfolio(args: dict) -> None:
    if not _require_login():
        return
    base = args.get("base", "USD")
    try:
        data = usecases.show_portfolio(_session.user.user_id, base)
    except CurrencyNotFoundError:
        print(f"Неизвестная базовая валюта '{base}'")
        return
    except ApiRequestError as exc:
        print(exc)
        return

    if not data["rows"]:
        print("Портфель пуст. Купите валюту командой buy.")
        return

    table = PrettyTable()
    table.field_names = ["Валюта", "Баланс", f"Стоимость ({data['base']})"]
    table.align = "r"
    for row in data["rows"]:
        table.add_row(
            [row["currency"], f"{row['balance']:.4f}", f"{row['value']:,.2f}"]
        )
    print(f"Портфель пользователя '{data['username']}' (база: {data['base']}):")
    print(table)
    print(f"ИТОГО: {data['total']:,.2f} {data['base']}")


def cmd_buy(args: dict) -> None:
    if not _require_login():
        return
    currency = args.get("currency")
    amount = _parse_amount(args.get("amount"))
    if not currency or amount is None:
        print("Использование: buy --currency <CODE> --amount <N>")
        return
    try:
        result = usecases.buy(_session.user.user_id, currency, amount)
    except (CurrencyNotFoundError, ValueError, InsufficientFundsError) as exc:
        print(exc)
        return

    code = result["code"]
    print(f"Покупка выполнена: {result['amount']:.4f} {code}")
    print("Изменения в портфеле:")
    print(f"- {code}: было {result['before']:.4f} → стало {result['after']:.4f}")
    if result["cost_usd"] is not None:
        print(f"Оценочная стоимость покупки: {result['cost_usd']:,.2f} USD")


def cmd_sell(args: dict) -> None:
    if not _require_login():
        return
    currency = args.get("currency")
    amount = _parse_amount(args.get("amount"))
    if not currency or amount is None:
        print("Использование: sell --currency <CODE> --amount <N>")
        return
    try:
        result = usecases.sell(_session.user.user_id, currency, amount)
    except CurrencyNotFoundError:
        print(
            f"У вас нет кошелька '{currency.upper()}'. "
            f"Он создаётся автоматически при первой покупке."
        )
        return
    except (ValueError, InsufficientFundsError) as exc:
        print(exc)
        return

    code = result["code"]
    print(f"Продажа выполнена: {result['amount']:.4f} {code}")
    print("Изменения в портфеле:")
    print(f"- {code}: было {result['before']:.4f} → стало {result['after']:.4f}")
    if result["revenue_usd"] is not None:
        print(f"Оценочная выручка: {result['revenue_usd']:,.2f} USD")


def cmd_get_rate(args: dict) -> None:
    from_code = args.get("from")
    to_code = args.get("to")
    if not from_code or not to_code:
        print("Использование: get-rate --from <CODE> --to <CODE>")
        return
    try:
        rate = usecases.get_rate(from_code, to_code)
    except CurrencyNotFoundError as exc:
        print(exc)
        return
    except ApiRequestError as exc:
        print(exc)
        return

    print(
        f"Курс {rate['from']}→{rate['to']}: {rate['rate']:.8f} "
        f"(обновлено: {rate['updated_at']})"
    )
    if rate["stale"]:
        print("Внимание: курс устарел. Выполните update-rates.")


def cmd_update_rates(args: dict) -> None:
    source = args.get("source")
    print("Starting rates update...")
    result = RatesUpdater().run_update(source=source)
    if not result.get("rates"):
        print("Не удалось обновить курсы.")
        return
    print(f"Обновлено курсов: {result['saved']}")
    if result.get("errors"):
        print("Ошибки источников:")
        for err in result["errors"]:
            print(f"  - {err['source']}: {err['error']}")
    print(f"Last refresh: {result.get('last_refresh', 'n/a')}")


def cmd_show_rates(args: dict) -> None:
    snapshot = _db.read_json(_db.rates_path, default={"pairs": {}})
    pairs = snapshot.get("pairs", {})
    if not pairs:
        print(
            "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
        )
        return

    currency = args.get("currency")
    top = args.get("top")

    items = list(pairs.items())

    if currency:
        cur = currency.upper()
        items = [
            (k, v) for k, v in items if k.startswith(f"{cur}_") or k.endswith(f"_{cur}")
        ]
        if not items:
            print(f"Курс для '{cur}' не найден в кеше.")
            return

    if top is not None:
        try:
            n = int(top)
        except ValueError:
            print("--top должен быть целым числом")
            return
        items.sort(key=lambda kv: kv[1].get("rate", 0), reverse=True)
        items = items[:n]
    else:
        items.sort(key=lambda kv: kv[0])

    print(f"Rates from cache (updated at {snapshot.get('last_refresh', 'n/a')}):")
    table = PrettyTable()
    table.field_names = ["Пара", "Курс", "Источник", "Обновлено"]
    for key, info in items:
        table.add_row(
            [
                key,
                f"{info.get('rate', 0):.6f}",
                info.get("source", "-"),
                info.get("updated_at", "-"),
            ]
        )
    print(table)


# ---------- инфраструктура REPL ----------

COMMANDS = {
    "register": cmd_register,
    "login": cmd_login,
    "show-portfolio": cmd_show_portfolio,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "get-rate": cmd_get_rate,
    "update-rates": cmd_update_rates,
    "show-rates": cmd_show_rates,
}

HELP_TEXT = """Доступные команды:
  register --username <name> --password <pass>
  login --username <name> --password <pass>
  show-portfolio [--base <CODE>]
  buy --currency <CODE> --amount <N>
  sell --currency <CODE> --amount <N>
  get-rate --from <CODE> --to <CODE>
  update-rates [--source <coingecko|exchangerate>]
  show-rates [--currency <CODE>] [--top <N>]
  help, exit"""


def _require_login() -> bool:
    if not _session.is_logged_in:
        print("Сначала выполните login")
        return False
    return True


def _parse_amount(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_args(tokens: list[str]) -> dict:
    """Парсит ['--username', 'alice', '--password', '1234'] в {'username': 'alice', ...}."""
    args: dict = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                args[key] = tokens[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


def main() -> None:
    """Точка входа CLI. Запускает REPL."""
    setup_logging()
    print("ValutaTrade Hub. Введите 'help' для списка команд, 'exit' для выхода.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line == "help":
            print(HELP_TEXT)
            continue

        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            print(f"Ошибка разбора команды: {exc}")
            continue

        if not tokens:
            continue

        cmd_name, *rest = tokens
        handler = COMMANDS.get(cmd_name)
        if handler is None:
            print(f"Неизвестная команда: {cmd_name}. Введите 'help'.")
            continue

        try:
            handler(_parse_args(rest))
        except Exception as exc:  # noqa: BLE001
            print(f"Ошибка: {exc}")


if __name__ == "__main__":
    main()
