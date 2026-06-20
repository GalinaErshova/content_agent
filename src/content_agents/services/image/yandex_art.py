"""
services/image/yandex_art.py — настоящий адаптер YandexART.

Особенность: API YandexART асинхронный. Схема такая:
1) POST с промптом → получаем id операции;
2) опрашиваем операцию, пока не завершится;
3) забираем картинку (приходит в base64) и декодируем в байты.

Всю эту возню адаптер прячет внутри: снаружи остаётся простой метод
generate(prompt) -> bytes, как того требует порт ImageProvider.

Требует сети и ключей. Без них — MockImageProvider.
"""

from __future__ import annotations

import base64
import os
import time

import requests

GENERATE_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
OPERATION_URL = "https://llm.api.cloud.yandex.net/operations/{op_id}"


class YandexARTAdapter:
    """Реализует порт ImageProvider поверх асинхронного API YandexART."""

    def __init__(self, api_key: str | None = None, folder_id: str | None = None,
                 poll_interval: float = 2.0, max_wait: float = 60.0):
        self.api_key = api_key or os.environ["YC_API_KEY"]
        self.folder_id = folder_id or os.environ["YC_FOLDER_ID"]
        self.poll_interval = poll_interval     # пауза между опросами операции
        self.max_wait = max_wait               # сколько максимум ждать готовности

    def _headers(self) -> dict:
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }

    def generate(self, prompt: str, **opts) -> bytes:
        # Шаг 1: запускаем генерацию, получаем id операции.
        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {"aspectRatio": {"widthRatio": "16", "heightRatio": "9"}},
            "messages": [{"weight": 1, "text": prompt}],
        }
        resp = requests.post(GENERATE_URL, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        op_id = resp.json()["id"]

        # Шаг 2: опрашиваем операцию, пока done != True (или не истечёт max_wait).
        waited = 0.0
        while waited < self.max_wait:
            op = requests.get(OPERATION_URL.format(op_id=op_id), headers=self._headers(), timeout=30)
            op.raise_for_status()
            data = op.json()
            if data.get("done"):
                # Шаг 3: картинка лежит в response.image как base64.
                image_b64 = data["response"]["image"]
                return base64.b64decode(image_b64)
            time.sleep(self.poll_interval)
            waited += self.poll_interval

        raise TimeoutError(f"YandexART не успел сгенерировать за {self.max_wait} с")
