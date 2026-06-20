"""
services/image/mock.py — поддельный генератор изображений (без сети).

Рисует простой PNG-плейсхолдер с подписью средствами стандартной библиотеки
(модуль никаких сторонних пакетов не требует — формирует валидный PNG вручную).
Этого достаточно, чтобы Illustrator реально создавал файлы и они попадали
в итоговый материал. Настоящий YandexART рисует осмысленные картинки.
"""

from __future__ import annotations

import struct
import zlib


class MockImageProvider:
    """Реализует порт ImageProvider. Возвращает байты крошечного PNG."""

    def generate(self, prompt: str, **opts) -> bytes:
        # Генерируем однотонный PNG фиксированного размера. Цвет зависит от длины
        # промпта — чтобы разные иллюстрации визуально отличались.
        width, height = 320, 180
        r = (len(prompt) * 37) % 200 + 30
        g = (len(prompt) * 53) % 200 + 30
        b = (len(prompt) * 71) % 200 + 30
        return _solid_png(width, height, (r, g, b))


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Собрать минимальный валидный PNG одного цвета (без внешних библиотек)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8 бит, truecolor
    row = b"\x00" + bytes(rgb) * width                            # фильтр 0 + пиксели строки
    raw = row * height
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
