# ValutaTrade Hub

Консольное приложение-симулятор валютного кошелька с парсером курсов фиатных и криптовалют.

## Стек

- Python 3.12
- uv — управление зависимостями и окружением
- ruff — линтер и форматтер
- prettytable — форматированный вывод таблиц
- requests — HTTP-запросы к API

## Структура

```
valutatrade_hub/
├── core/              # бизнес-логика: модели, usecases, валюты, исключения
├── infra/             # Singleton: SettingsLoader, DatabaseManager
├── parser_service/    # парсер курсов: API-клиенты, storage, updater, scheduler
├── cli/               # интерфейс командной строки (REPL)
├── decorators.py      # @log_action — логирование операций
└── logging_config.py  # настройка логов (RotatingFileHandler)

data/                  # runtime JSON: users, portfolios, rates, exchange_rates
logs/                  # runtime логи: actions.log
```

## Установка

```bash
git clone <repo-url>
cd finalproject_Vorovskoy_26-555
uv sync
```

## Настройка API-ключа

Зарегистрируйтесь на [exchangerate-api.com](https://www.exchangerate-api.com/), получите ключ и создайте `.env` в корне:

```
EXCHANGERATE_API_KEY=your_api_key_here
```

Образец — в `.env.example`. Файл `.env` в `.gitignore` и в репозиторий не попадает.

## Запуск

```bash
uv run valutatrade
# или
uv run python main.py
```

## Команды CLI

| Команда | Назначение |
|---|---|
| `register --username X --password Y` | регистрация нового пользователя |
| `login --username X --password Y` | вход в систему |
| `show-portfolio [--base USD]` | портфель с итоговой стоимостью |
| `buy --currency BTC --amount 0.05` | покупка валюты |
| `sell --currency BTC --amount 0.01` | продажа валюты |
| `get-rate --from USD --to BTC` | курс валюты |
| `update-rates [--source coingecko\|exchangerate]` | обновить курсы из внешних API |
| `show-rates [--currency BTC] [--top 3]` | показать курсы из локального кеша |
| `help`, `exit` | справка / выход |

## Parser Service

- **CoinGecko** — криптовалюты (BTC, ETH, SOL), без ключа.
- **ExchangeRate-API** — фиатные валюты (EUR, GBP, RUB), нужен ключ.
- Курсы сохраняются в `data/rates.json` (снимок, TTL 5 минут) и `data/exchange_rates.json` (история).
- Запись атомарная (tmp → rename), один упавший источник не блокирует остальные.

## Качество кода

```bash
uv run ruff check .
uv run ruff format --check .
```

## Что реализовано

- ООП: `User`, `Wallet`, `Portfolio` с приватными полями и property-валидацией.
- Иерархия валют: ABC `Currency` + `FiatCurrency` + `CryptoCurrency` + фабрика `get_currency()`.
- Доменные исключения: `InsufficientFundsError`, `CurrencyNotFoundError`, `ApiRequestError`.
- Singleton: `SettingsLoader` (конфиг) и `DatabaseManager` (JSON-хранилище).
- Декоратор `@log_action` для трассировки BUY/SELL/REGISTER/LOGIN.
- Логирование: `RotatingFileHandler`, формат с ISO-timestamp.
- Parser Service: 2 API-клиента, atomic write, история курсов.
- CLI на `shlex` с 8 командами и REPL.