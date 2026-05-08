# payment.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import secrets

from database import db
from config import ADMIN_IDS

router = Router()

# Цены на тарифы
PRICES = {
    "1day": {"name": "1 день", "days": 1, "price": 15},
    "7days": {"name": "7 дней", "days": 7, "price": 30},
    "30days": {"name": "30 дней", "days": 30, "price": 70},
    "365days": {"name": "365 дней", "days": 365, "price": 100}
}

# Реквизиты
CARD_NUMBER = "2202 2068 9836 0289"
CARD_HOLDER = "Сбербанк"

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

def get_tariff_keyboard():
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📅 1 день - 15 ₽", callback_data="tariff_1day")],
        [types.InlineKeyboardButton(text="📅 7 дней - 30 ₽", callback_data="tariff_7days")],
        [types.InlineKeyboardButton(text="📅 30 дней - 70 ₽", callback_data="tariff_30days")],
        [types.InlineKeyboardButton(text="📅 365 дней - 100 ₽", callback_data="tariff_365days")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])
    return keyboard

@router.message(Command("buy"))
async def cmd_buy(message: types.Message):
    await message.answer(
        "💎 <b>Выбери тариф:</b>\n\n"
        "1 день - 15 ₽\n7 дней - 30 ₽\n30 дней - 70 ₽\n365 дней - 100 ₽",
        parse_mode="HTML",
        reply_markup=get_tariff_keyboard()
    )

@router.callback_query(lambda c: c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff_code = callback.data.replace("tariff_", "")
    
    if tariff_code not in PRICES:
        await callback.answer("Ошибка")
        return
    
    tariff = PRICES[tariff_code]
    await state.update_data(tariff_code=tariff_code, tariff_name=tariff["name"], price=tariff["price"])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="paid")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])
    
    await callback.message.edit_text(
        f"💳 <b>Оплата: {tariff['name']} - {tariff['price']} ₽</b>\n\n"
        f"🏦 <b>Реквизиты:</b>\n<code>{CARD_NUMBER}</code>\nКарта Сбербанка\n\n"
        f"📌 В комментарии укажи ID: <code>{callback.from_user.id}</code>\n\n"
        f"После оплаты нажми «Я оплатил(а)» и отправь чек",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await state.set_state(PaymentStates.waiting_for_receipt)
    await callback.answer()

@router.callback_query(lambda c: c.data == "paid")
async def paid_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📸 <b>Отправь чек об оплате</b>\n\n"
        "Пришли скриншот или фото чека из банка.\n"
        "Админ проверит и выдаст ключ.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(PaymentStates.waiting_for_receipt)
async def handle_receipt(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Отправь фото чека")
        return
    
    data = await state.get_data()
    tariff_code = data.get("tariff_code")
    tariff_name = data.get("tariff_name")
    price = data.get("price")
    
    if not tariff_code:
        await message.answer("❌ Ошибка: начни заново командой /buy")
        await state.clear()
        return
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Сохраняем заказ
    cursor = db.conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, username, tariff, price, receipt_url, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (message.from_user.id, message.from_user.username or "no_username", tariff_code, price, file_id))
    db.conn.commit()
    order_id = cursor.lastrowid
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order_id}"),
                    types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")
                ]
            ])
            
            await message.bot.send_photo(
                admin_id,
                photo=file_id,
                caption=f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
                       f"👤 @{message.from_user.username or message.from_user.id}\n"
                       f"🆔 ID: {message.from_user.id}\n"
                       f"📦 {tariff_name}\n"
                       f"💰 {price} ₽",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except:
            pass
    
    await message.answer(
        "✅ <b>Чек отправлен!</b>\n\n"
        "Админ проверит оплату и выдаст ключ.\n"
        "Обычно это занимает 5-15 минут.",
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
async def handle_admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    action, order_id = callback.data.split("_")
    order_id = int(order_id)
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if not order or order["status"] != "pending":
        await callback.answer("Заказ уже обработан")
        return
    
    if action == "approve":
        days_map = {"1day": 1, "7days": 7, "30days": 30, "365days": 365}
        days = days_map.get(order["tariff"], 30)
        
        raw_key = secrets.token_hex(8).upper()
        
        cursor.execute("""
            INSERT INTO license_keys (key, plan, days, created_by)
            VALUES (?, ?, ?, ?)
        """, (raw_key, order["tariff"], days, callback.from_user.id))
        
        cursor.execute("""
            UPDATE orders SET status = 'approved', key_generated = ? WHERE id = ?
        """, (raw_key, order_id))
        db.conn.commit()
        
        await callback.bot.send_message(
            order["user_id"],
            f"✅ <b>Заказ #{order_id} одобрен!</b>\n\n"
            f"🔑 <b>Ваш ключ:</b>\n<code>{raw_key}</code>\n\n"
            f"📝 Активация: <code>/activate {raw_key} ТВОЙ_HWID</code>",
            parse_mode="HTML"
        )
        
        await callback.message.edit_caption(
            caption=f"✅ <b>Заказ #{order_id} ОДОБРЕН</b>\nКлюч: {raw_key}",
            parse_mode="HTML"
        )
        await callback.answer("✅ Ключ выдан")
    else:
        cursor.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        db.conn.commit()
        
        await callback.bot.send_message(
            order["user_id"],
            f"❌ <b>Заказ #{order_id} отклонен</b>\n\n"
            f"Причина: оплата не подтверждена.\nПопробуй снова /buy",
            parse_mode="HTML"
        )
        await callback.message.edit_caption(caption=f"❌ Заказ #{order_id} ОТКЛОНЕН")
        await callback.answer("❌ Отклонен")

@router.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Оплата отменена")
    await callback.answer()
