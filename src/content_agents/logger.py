"""
logger.py — крошечная обёртка над стандартным модулем logging.

Зачем отдельный файл: чтобы во всём проекте логгер настраивался в одном месте
и одинаково. Если позже захотите писать логи в файл или менять формат — правка
только здесь.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Вернуть настроенный логгер. name обычно = __name__ модуля-вызывателя."""
    logger = logging.getLogger(name)
    if not logger.handlers:                         # настраиваем один раз, чтобы не дублировать вывод
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
