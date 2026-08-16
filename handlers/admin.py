from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database as db
import keyboards as kb

router = Router()


class AdminForm(StatesGroup):
    waiting_master_id = State()
    waiting_remove_id = State()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_USER_IDS


def admin_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Додати майстра", callback_data="admin:add")
    builder.button(text="➖ Видалити майстра", callback_data="admin:remove")
    builder.button(text="👥 Список майстрів", callback_data="admin:list")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


async def show_admin_menu(message: Message):
    await message.answer(
        "⚙️ <b>Адміністрування доступу</b>\n\n"
        "Тут можна додавати та видаляти майстрів без редагування .env.\n"
        "Потрібен саме Telegram ID користувача.",
        reply_markup=admin_menu(),
    )


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ця команда доступна тільки адміністратору.")
        return
    await state.clear()
    await show_admin_menu(message)


@router.message(F.text == "👑 Адміністрування")
async def admin_button(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await show_admin_menu(message)


@router.callback_query(F.data == "admin:add")
async def admin_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Немає доступу", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_master_id)
    await call.message.answer(
        "➕ <b>Додати майстра</b>\n\n"
        "Надішли Telegram ID майстра одним числом.\n"
        "Наприклад: <code>123456789</code>\n\n"
        "Дізнатись ID можна через @userinfobot.\n"
        "Для скасування натисни «❌ Скасувати»."
    )
    await call.answer()


@router.message(AdminForm.waiting_master_id)
async def admin_add_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ ID має складатися тільки з цифр. Спробуй ще раз.")
        return
    user_id = int(raw)
    if user_id in config.ADMIN_USER_IDS:
        await message.answer("ℹ️ Цей ID вже є адміністратором.")
        await state.clear()
        return
    await db.add_master(user_id, message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ Майстра <code>{user_id}</code> додано.\n\n"
        "Тепер він може натиснути /start і користуватися ботом.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "admin:remove")
async def admin_remove(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Немає доступу", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_remove_id)
    await call.message.answer(
        "➖ <b>Видалити майстра</b>\n\n"
        "Надішли Telegram ID майстра, якому треба забрати доступ."
    )
    await call.answer()


@router.message(AdminForm.waiting_remove_id)
async def admin_remove_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ ID має складатися тільки з цифр. Спробуй ще раз.")
        return
    user_id = int(raw)
    if user_id in config.ADMIN_USER_IDS:
        await message.answer("⛔ Не можна видалити адміністратора через цей розділ.")
        await state.clear()
        return
    if not await db.is_master(user_id):
        await message.answer("ℹ️ Цього ID немає серед майстрів.")
        await state.clear()
        return
    await db.remove_master(user_id)
    await state.clear()
    await message.answer(
        f"✅ Доступ для <code>{user_id}</code> видалено.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "admin:list")
async def admin_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Немає доступу", show_alert=True)
        return
    masters = await db.list_masters()
    lines = ["👥 <b>Майстри з доступом</b>", ""]
    if masters:
        lines.extend(f"• <code>{m['user_id']}</code>" for m in masters)
    else:
        lines.append("Поки що жодного майстра не додано.")
    lines.append("")
    lines.append("Адміністратори зберігаються в ADMIN_USER_IDS у .env.")
    await call.message.answer("\n".join(lines), reply_markup=admin_menu())
    await call.answer()


@router.callback_query(F.data == "admin:back")
async def admin_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Немає доступу", show_alert=True)
        return
    await state.clear()
    await call.message.answer("Головне меню", reply_markup=kb.main_menu())
    await call.answer()
