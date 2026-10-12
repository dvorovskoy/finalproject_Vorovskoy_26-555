"""Вспомогательные функции и валидаторы."""


def validate_currency_code(code: str) -> str:
    """Проверяет и нормализует код валюты (верхний регистр, 2–5 символов)."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    code = code.upper().strip()
    if not (2 <= len(code) <= 5) or " " in code:
        raise ValueError(f"Некорректный код валюты: '{code}'")
    return code


def validate_amount(amount: float) -> float:
    """Проверяет, что сумма — положительное число."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("Сумма должна быть числом")
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    return float(amount)


def validate_username(username: str) -> str:
    """Проверяет, что имя пользователя не пустое."""
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    return username.strip()


def validate_password(password: str) -> str:
    """Проверяет, что пароль не короче 4 символов."""
    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")
    return password