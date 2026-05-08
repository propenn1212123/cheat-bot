# admin_panel.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import secrets
from datetime import datetime

from database import db
from config import ADMIN_IDS

router = Router()

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_hwid_ban = State()
    waiting_for_hwid_unban = State()
    waiting_for_hwid_clear = State()
    waiting_for_hwid_deactivate = State()
    waiting_for_key_delete = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Главное меню админа
@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🔒 Бан HWID", callback_data="admin_ban"),
            types.InlineKeyboardButton(text="🔓 Разбан HWID", callback_data="admin_unban")
        ],
        [
            types.InlineKeyboardButton(text="🧹 Очистить HWID", callback_data="admin_clear"),
            types.InlineKeyboardButton(text="❌ Деактив. подписку", callback_data="admin_deactivate")
        ],
        [
            types.InlineKeyboardButton(text="🔑 Создать ключ", callback_data="admin_genkey"),
            types.InlineKeyboardButton(text="🗑️ Удалить ключ", callback_data="admin_delkey")
        ],
        [
            types.InlineKeyboardButton(text="📋 Список ключей", callback_data="admin_keys"),
            types.InlineKeyboardButton(text="👥 Список юзеров", callback_data="admin_users")
        ],
        [
            types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ]
    ])
    
    await message.answer(
        "👑 <b>Админ-панель управления</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# Обработка нажатий на кнопки
@router.callback_query(lambda c: c.data.startswith("admin_"))
async def admin_callback(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    action = callback.data.replace("admin_", "")
    
    if action == "ban":
        await callback.message.answer(
            "🔒 <b>Блокировка HWID</b>\n\n"
            "Введи HWID и причину через пробел:\n"
            "<code>ABC123DEF456 Нарушение правил</code>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_hwid_ban)
    
    elif action == "unban":
        await callback.message.answer(
            "🔓 <b>Разблокировка HWID</b>\n\n"
            "Введи HWID для разблокировки:\n"
            "<code>ABC123DEF456</code>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_hwid_unban)
    
    elif action == "clear":
        await callback.message.answer(
            "🧹 <b>Очистка HWID</b>\n\n"
            "Введи Telegram ID пользователя:\n"
            "<code>123456789</code>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_hwid_clear)
    
    elif action == "deactivate":
        await callback.message.answer(
            "❌ <b>Деактивация подписки</b>\n\n"
            "Введи HWID пользователя:\n"
            "<code>ABC123DEF456</code>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_hwid_deactivate)
    
    elif action == "genkey":
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="1 день", callback_data="gen_1day")],
            [types.InlineKeyboardButton(text="7 дней", callback_data="gen_7days")],
            [types.InlineKeyboardButton(text="30 дней", callback_data="gen_30days")],
            [types.InlineKeyboardButton(text="90 дней", callback_data="gen_90days")],
            [types.InlineKeyboardButton(text="365 дней", callback_data="gen_365days")],
            [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(
            "🔑 <b>Выбери срок ключа:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    elif action == "delkey":
        await callback.message.answer(
            "🗑️ <b>Удаление ключа</b>\n\n"
            "Введи ключ для удаления:\n"
            "<code>A7F3D9C2B4E6F1A8</code>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_key_delete)
    
    elif action == "keys":
        keys = await db.get_all_keys(limit=30)
        if not keys:
            text = "📭 Ключей нет"
        else:
            text = "🔑 <b>Список ключей:</b>\n\n"
            for k in keys:
                status = "✅ Свободен" if k["used_by"] is None else f"❌ Использован"
                text += f"<code>{k['key']}</code> | {k['plan']} | {status}\n"
        
        await callback.message.edit_text(
            text[:4000],
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )
    
    elif action == "users":
        users = await db.get_all_users(limit=30)
        if not users:
            text = "👥 Пользователей нет"
        else:
            text = "👥 <b>Список пользователей:</b>\n\n"
            for u in users:
                status = "✅ Активен" if u["is_active"] and not u["is_banned"] else "❌ Забанен"
                hwid = u["hwid"][:16] + "..." if u["hwid"] and len(u["hwid"]) > 16 else (u["hwid"] or "Нет")
                text += f"ID: {u['user_id']} | @{u['username'] or 'Нет'} | HWID: {hwid} | {status}\n"
        
        await callback.message.edit_text(
            text[:4000],
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )
    
    elif action == "stats":
        stats = await db.get_stats()
        text = f"📊 <b>Статистика:</b>\n\n"
        text += f"👥 Всего юзеров: {stats['total_users']}\n"
        text += f"✅ Активных: {stats['active_subs']}\n"
        text += f"🚫 Забанено: {stats['banned_users']}\n"
        text += f"🔑 Всего ключей: {stats['total_keys']}\n"
        text += f"🔑 Использовано: {stats['used_keys']}\n"
        text += f"🔒 Забанено HWID: {stats['banned_hwid']}"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )
    
    elif action == "back":
        await admin_panel(callback.message)
    
    await callback.answer()

# Генерация ключей
@router.callback_query(lambda c: c.data.startswith("gen_"))
async def generate_key(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    
    plan_data = {
        "1day": ("1_day", 1),
        "7days": ("7_days", 7),
        "30days": ("1_month", 30),
        "90days": ("3_months", 90),
        "365days": ("1_year", 365)
    }
    
    plan_type = callback.data.replace("gen_", "")
    if plan_type not in plan_data:
        await callback.answer("Ошибка")
        return
    
    plan_name, days = plan_data[plan_type]
    raw_key = secrets.token_hex(8).upper()
    
    success = await db.create_key(raw_key, plan_name, days, callback.from_user.id)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Ключ создан!</b>\n\n"
            f"🔑 <code>{raw_key}</code>\n"
            f"📦 Тариф: {plan_name} ({days} дней)\n\n"
            f"Пользователь активирует:\n"
            f"<code>/activate {raw_key} ЕГО_HWID</code>",
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )
    else:
        await callback.message.edit_text("❌ Ошибка при создании ключа")
    
    await callback.answer()

# Обработка ввода от админа
@router.message(AdminStates.waiting_for_hwid_ban)
async def process_ban(message: types.Message, state: FSMContext):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Формат: HWID причина")
        return
    
    hwid, reason = parts[0], parts[1]
    success = await db.ban_hwid(hwid, message.from_user.id, reason)
    
    if success:
        await message.answer(f"✅ HWID <code>{hwid}</code> заблокирован\nПричина: {reason}", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка блокировки")
    
    await state.clear()
    await admin_panel(message)

@router.message(AdminStates.waiting_for_hwid_unban)
async def process_unban(message: types.Message, state: FSMContext):
    hwid = message.text.strip()
    success = await db.unban_hwid(hwid)
    
    if success:
        await message.answer(f"✅ HWID <code>{hwid}</code> разблокирован", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка")
    
    await state.clear()
    await admin_panel(message)

@router.message(AdminStates.waiting_for_hwid_clear)
async def process_clear(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await db.clear_hwid(user_id)
        await message.answer(f"✅ HWID очищен у {user_id}")
    except:
        await message.answer("❌ Введи корректный ID")
    
    await state.clear()
    await admin_panel(message)

@router.message(AdminStates.waiting_for_hwid_deactivate)
async def process_deactivate(message: types.Message, state: FSMContext):
    hwid = message.text.strip()
    await db.deactivate_subscription(hwid)
    await message.answer(f"✅ Подписка деактивирована для HWID <code>{hwid}</code>", parse_mode="HTML")
    await state.clear()
    await admin_panel(message)

@router.message(AdminStates.waiting_for_key_delete)
async def process_delete_key(message: types.Message, state: FSMContext):
    key = message.text.strip().upper()
    await db.delete_key(key)
    await message.answer(f"✅ Ключ <code>{key}</code> удалён", parse_mode="HTML")
    await state.clear()
    await admin_panel(message)