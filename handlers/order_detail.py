import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from states import DentForm
from pdf_generator import generate_act

router = Router()


# ---------- додати вм'ятину до існуючого замовлення ----------

@router.callback_query(F.data.startswith("order_adddent:"))
async def order_add_dent(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(DentForm.element)

    from handlers.calculator import build_card_text
    card = await callback.message.answer(
        build_card_text({}, "Оберіть пошкоджений елемент:"),
        reply_markup=kb.element_kb(),
    )
    await state.update_data(
        order_id=order_id, new_order=False,
        card_chat_id=card.chat.id, card_message_id=card.message_id,
    )
    await callback.answer()


# ---------- видалення окремої вм'ятини ----------

@router.callback_query(F.data.startswith("order_dents:"))
async def order_dents_list(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    dents = await db.list_dents(order_id)
    if not dents:
        await callback.answer("Вм'ятин немає.", show_alert=True)
        return
    await callback.message.answer(
        "Оберіть вм'ятину для видалення:",
        reply_markup=kb.dents_delete_kb(order_id, dents),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dent_delete:"))
async def dent_delete(callback: CallbackQuery):
    _, dent_id, order_id = callback.data.split(":")
    await db.delete_dent(int(dent_id))
    await callback.answer("Вм'ятину видалено")
    from handlers.calculator import show_order_card
    await callback.message.delete()
    await show_order_card(callback.message, int(order_id))


# ---------- акт (PDF) ----------

@router.callback_query(F.data.startswith("order_act:"))
async def order_act(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)
    dents = await db.list_dents(order_id)

    if not dents:
        await callback.answer("У замовленні ще немає жодної вм'ятини.", show_alert=True)
        return

    os.makedirs("acts", exist_ok=True)
    out_path = f"acts/act_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    generate_act(order, dents, out_path)

    await callback.message.answer_document(
        FSInputFile(out_path),
        caption=f"📄 Акт виконаних робіт по замовленню #{order_id}",
    )
    await callback.answer()


# ---------- завершити замовлення ----------

@router.callback_query(F.data.startswith("order_complete:"))
async def order_complete(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await db.update_order_field(order_id, "status", "completed")
    await db.update_order_field(order_id, "completed_at", datetime.now().isoformat(timespec="seconds"))
    await callback.answer("Замовлення завершено ✅")
    from handlers.calculator import show_order_card
    await callback.message.delete()
    await show_order_card(callback.message, order_id)


# ---------- видалення замовлення (з підтвердженням) ----------

@router.callback_query(F.data.startswith("order_delete:"))
async def order_delete_ask(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    kb_confirm = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"order_delete_yes:{order_id}"),
        InlineKeyboardButton(text="❌ Ні", callback_data="order_delete_no"),
    ]])
    await callback.message.answer(
        f"Точно видалити замовлення #{order_id}? Цю дію не можна скасувати.",
        reply_markup=kb_confirm,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_delete_yes:"))
async def order_delete_confirmed(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await db.delete_order(order_id)
    await callback.message.edit_text(f"🗑 Замовлення #{order_id} видалено.")
    await callback.answer()


@router.callback_query(F.data == "order_delete_no")
async def order_delete_cancelled(callback: CallbackQuery):
    await callback.message.edit_text("Видалення скасовано.")
    await callback.answer()
