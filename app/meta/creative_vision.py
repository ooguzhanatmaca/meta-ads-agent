"""Vision-based creative critique for Meta ad images via Gemini (LiteLLM).

Downloads the ad's creative image and asks a vision-capable model for concise,
actionable Turkish feedback. Read-only — it only reads the image and returns text.
"""

import base64
import os

import requests


DEFAULT_VISION_MODEL = "gemini/gemini-2.5-flash"
DOWNLOAD_TIMEOUT_SECONDS = 20

CRITIQUE_PROMPT = """Sen deneyimli bir performans pazarlama kreatif uzmanısın.
Bu Meta (Facebook/Instagram) reklam görselini değerlendir. Kısa, net ve
uygulanabilir Türkçe geri bildirim ver. Şu başlıkları kullan:

1. İlk izlenim (akışta dikkat çeker mi?)
2. Güçlü yönler
3. Zayıf yönler (kontrast, metin yoğunluğu, ürün görünürlüğü, marka, okunabilirlik)
4. Somut iyileştirme önerileri (madde madde)

Yalnızca gördüğün görsele dayan; veri uydurma."""


def _download_image_data_url(url: str) -> str:
    """Download an image and return it as a base64 data URL."""
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def critique_image(image_url: str, prompt: str = CRITIQUE_PROMPT) -> str:
    """Return a vision-model critique of the given image URL."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil; görsel analizi yapılamıyor.")

    import litellm

    model = os.getenv("VISION_MODEL", DEFAULT_VISION_MODEL)
    data_url = _download_image_data_url(image_url)
    response = litellm.completion(
        model=model,
        api_key=api_key,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    content = response.choices[0].message.content
    return content or "Görsel analiz sonucu boş döndü."
