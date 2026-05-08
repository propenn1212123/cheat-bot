# hwid_api.py
from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import asyncio
from database import db

app = Flask(__name__)

# Инициализация БД при старте
@app.before_first_request
def init_db():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(db.init())

@app.route('/check_hwid', methods=['POST'])
def check_hwid():
    """Эндпоинт для проверки HWID читом"""
    data = request.get_json()
    
    if not data or 'hwid' not in data:
        return jsonify({'error': 'No HWID provided'}), 400
    
    hwid = data['hwid']
    
    # Синхронная проверка (оборачиваем async)
    conn = sqlite3.connect('cheat_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Проверяем бан
    cursor.execute("SELECT * FROM banned_hwid WHERE hwid = ?", (hwid,))
    banned = cursor.fetchone()
    
    if banned:
        conn.close()
        return jsonify({
            'access': False,
            'message': f'HWID заблокирован. Причина: {banned["reason"]}'
        })
    
    # Проверяем подписку
    cursor.execute("SELECT * FROM users WHERE hwid = ?", (hwid,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({
            'access': False,
            'message': 'HWID не зарегистрирован. Купи ключ!'
        })
    
    if user['is_banned']:
        conn.close()
        return jsonify({
            'access': False,
            'message': f'Пользователь заблокирован. Причина: {user["ban_reason"]}'
        })
    
    # Проверяем дату подписки
    if user['subscribed_until']:
        until = datetime.fromisoformat(user['subscribed_until'])
        if until < datetime.now():
            conn.close()
            return jsonify({
                'access': False,
                'message': 'Срок подписки истёк. Купи новый ключ!'
            })
    
    conn.close()
    return jsonify({
        'access': True,
        'message': 'Доступ разрешён',
        'expires': user['subscribed_until']
    })

@app.route('/register_hwid', methods=['POST'])
def register_hwid():
    """Регистрация нового HWID (если не хочешь через бота)"""
    data = request.get_json()
    
    if not data or 'hwid' not in data or 'key' not in data:
        return jsonify({'error': 'Missing data'}), 400
    
    hwid = data['hwid']
    key = data['key']
    user_id = data.get('user_id', 0)
    
    # Здесь логика активации (можно переиспользовать из database.py)
    # Упрощённо:
    conn = sqlite3.connect('cheat_bot.db')
    cursor = conn.cursor()
    
    # Проверяем ключ
    cursor.execute("SELECT * FROM license_keys WHERE key = ? AND used_by IS NULL", (key.upper(),))
    key_info = cursor.fetchone()
    
    if not key_info:
        conn.close()
        return jsonify({'error': 'Invalid key'}), 400
    
    # Активируем
    new_until = datetime.now().isoformat()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, hwid, subscribed_until, license_key) VALUES (?, ?, ?, ?)",
        (user_id, hwid, new_until, key.upper())
    )
    cursor.execute("UPDATE license_keys SET used_by = ?, used_hwid = ? WHERE key = ?", (user_id, hwid, key.upper()))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Активировано!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)