"""
Аналіз фото пошкодження авто через Anthropic API (Claude Vision).
Модель дивиться на фото і повертає JSON з типом та розміром пошкодження.
"""
import json
import base64
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY
from price_data import DAMAGE_TYPES, DAMAGE_SIZE

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = f"""Ти — експерт з оцінки кузовних пошкоджень автомобіля.
Тобі надсилають фото пошкодження. Визнач:
1. Тип пошкодження — обери ОДИН ключ зі списку: {list(DAMAGE_TYPES.keys())}
   (crack=тріщина, dent=вм'ятина, chip=скол фарби, scratch=подряпина,
   paint=потрібне повне фарбування, rust=корозія)
2. Розмір пошкодження — обери ОДИН ключ зі списку: {list(DAMAGE_SIZE.keys())}
   (small=до 5см, medium=5-20см, large=понад 20см)
3. Коротко (1-2 речення українською) опиши, що бачиш на фото.

Відповідай ЛИШЕ у форматі JSON, без жодного тексту навколо:
{{"damage_type": "...", "damage_size": "...", "description": "..."}}
"""


def analyze_damage_photo(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Надсилає фото у Claude Vision і повертає розпізнаний тип/розмір пошкодження.
    Якщо модель поверне щось незрозуміле — підставляються безпечні значення
    за замовчуванням (medium/scratch), а користувач далі зможе виправити вручну.
    """
    b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Проаналізуй пошкодження на цьому фото.",
                    },
                ],
            }
        ],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # На випадок, якщо модель обгорне JSON у ```json ... ```
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw_text)
        if result.get("damage_type") not in DAMAGE_TYPES:
            result["damage_type"] = "scratch"
        if result.get("damage_size") not in DAMAGE_SIZE:
            result["damage_size"] = "medium"
        return result
    except (json.JSONDecodeError, KeyError):
        return {
            "damage_type": "scratch",
            "damage_size": "medium",
            "description": "Не вдалося точно розпізнати пошкодження, "
                            "будь ласка, перевірте параметри вручну.",
        }
