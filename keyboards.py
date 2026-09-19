"""
Inline-клавіатури для покрокового діалогу.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from price_data import POPULAR_BRANDS, DAMAGE_TYPES, DAMAGE_SIZE, EXTRA_WORKS


def mode_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Надіслати фото пошкодження", callback_data="mode_photo")
    builder.button(text="✍️ Ввести дані вручну", callback_data="mode_manual")
    builder.adjust(1)
    return builder.as_markup()


def brands_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for brand in POPULAR_BRANDS:
        builder.button(text=brand, callback_data=f"brand_{brand}")
    builder.adjust(2)
    return builder.as_markup()


def damage_types_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, val in DAMAGE_TYPES.items():
        builder.button(text=val["label"], callback_data=f"dmg_{key}")
    builder.adjust(1)
    return builder.as_markup()


def damage_size_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, val in DAMAGE_SIZE.items():
        builder.button(text=val["label"], callback_data=f"size_{key}")
    builder.adjust(1)
    return builder.as_markup()


def extra_works_kb(selected: set[str]) -> InlineKeyboardMarkup:
    """Клавіатура з чекбоксами (мульти-вибір) для додаткових робіт."""
    builder = InlineKeyboardBuilder()
    for key, val in EXTRA_WORKS.items():
        prefix = "✅ " if key in selected else "◻️ "
        builder.button(
            text=f"{prefix}{val['label']} (+{val['price']} грн)",
            callback_data=f"extra_{key}",
        )
    builder.button(text="➡️ Готово, рахувати", callback_data="extra_done")
    builder.adjust(1)
    return builder.as_markup()


def confirm_ai_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Все вірно, продовжити", callback_data="ai_confirm")
    builder.button(text="✏️ Виправити вручну", callback_data="ai_correct")
    builder.adjust(1)
    return builder.as_markup()


def contact_request_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📞 Записатися на діагностику", callback_data="book_visit")
    builder.button(text="🔄 Новий розрахунок", callback_data="restart")
    builder.adjust(1)
    return builder.as_markup()
