import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = 'https://myteam.mail.ru/bot/v1'
users_state = {}

CITIES = ['Астана', 'Алматы', 'Шымкент']
LECTORS = ['Турманова Д.А.', 'Секулова Ш.Б.']
LINKS = {
    'Каталог залов': 'https://delicate-klepon-16140e.netlify.app/',
    'Консультация': 'https://example.com/consultation',
    'Явка на семинар': 'https://comforting-torrone-5273b1.netlify.app/'
}
OPTIONS = list(LINKS.keys()) + ['Финансовый отчет']

def send_message(chat_id, text, buttons=None):
    url = f'{BASE_URL}/messages/sendText'
    params = {'token': TOKEN}
    data = {'chatId': chat_id, 'text': text}
    if buttons:
        data['inlineKeyboardMarkup'] = {'inlineKeyboard': buttons}
    requests.post(url, params=params, json=data)

def option_buttons(options):
    # Each button in its own row for easy tap
    return [[{'text': opt, 'callbackData': opt}] for opt in options]

def send_options(chat_id):
    send_message(
        chat_id,
        "👋 Добро пожаловать! Я бот компании Astana Orleu.\nВыберите нужный раздел ниже:",
        buttons=option_buttons(OPTIONS)
    )
    users_state[chat_id] = {'step': 'choose_option'}

def start_report(chat_id):
    users_state[chat_id] = {'step': 'choose_city', 'data': {}}
    send_message(
        chat_id,
        "Выберите город:",
        buttons=option_buttons(CITIES)
    )

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    message = data.get('message')
    callback = data.get('callbackQuery')
    if message:
        chat_id = message['chat']['chatId']
        text = message.get('text', '').strip()
        process_message(chat_id, text)
    elif callback:
        chat_id = callback['message']['chat']['chatId']
        data_text = callback['data']
        process_message(chat_id, data_text, is_callback=True)
        # Answer callback to remove loading spinner (optional)
        answer_callback(callback['id'])
    return jsonify({"ok": True})

def answer_callback(callback_id):
    url = f'{BASE_URL}/messages/answerCallbackQuery'
    params = {'token': TOKEN}
    data = {'queryId': callback_id}
    requests.post(url, params=params, json=data)

def process_message(chat_id, text, is_callback=False):
    state = users_state.get(chat_id)
    if not state:
        send_options(chat_id)
        return

    step = state['step']
    data = state.get('data', {})

    if step == 'choose_option':
        if text in OPTIONS:
            selected = text
            if selected == 'Финансовый отчет':
                start_report(chat_id)
            else:
                send_message(chat_id, f"Вот ваша ссылка: {LINKS[selected]}")
                users_state.pop(chat_id, None)
        else:
            send_message(chat_id, "Пожалуйста, выберите кнопку ниже.", buttons=option_buttons(OPTIONS))

    elif step == 'choose_city':
        if text in CITIES:
            city = text
            data['city'] = city
            state['step'] = 'choose_lector'
            send_message(
                chat_id,
                f"Выбран город: {city}\nВыберите лектора:",
                buttons=option_buttons(LECTORS)
            )
        else:
            send_message(chat_id, "Пожалуйста, выберите город кнопкой ниже.", buttons=option_buttons(CITIES))

    elif step == 'choose_lector':
        if text in LECTORS:
            lector = text
            data['lector'] = lector
            state['step'] = 'enter_date'
            send_message(chat_id, f"Выбран лектор: {lector}\nВведите дату семинара (например, 30 мая):")
        else:
            send_message(chat_id, "Пожалуйста, выберите лектора кнопкой ниже.", buttons=option_buttons(LECTORS))

    elif step == 'enter_date':
        data['date'] = text.strip()
        state['step'] = 'enter_start_sum'
        send_message(chat_id, "Введите сумму на начало дня (тг):")

    elif step == 'enter_start_sum':
        if text.isdigit():
            data['start_sum'] = int(text)
            data['expenses'] = []
            state['step'] = 'enter_expense'
            send_message(
                chat_id,
                "Введите затраты в формате:\nОписание: сумма\nНапример:\nТакси до зала: 960\nДля завершения введите слово 'готово'"
            )
        else:
            send_message(chat_id, "Сумма должна быть числом без пробелов.")

    elif step == 'enter_expense':
        if text.lower() == 'готово':
            total_expenses = sum(e[1] for e in data['expenses'])
            remainder = data['start_sum'] - total_expenses
            report_lines = [
                f"г. {data['city']}",
                f"Лектор: {data['lector']}",
                f"{data['date']}\n",
                f"Сумма на начало дня:\n{data['start_sum']} тг\n",
                "Затраты:"
            ]
            for desc, amount in data['expenses']:
                report_lines.append(f"{desc}: {amount} тг")
            report_lines.append(f"\nИтого расходы: {total_expenses} тг")
            report_lines.append(f"Сумма остатка: {remainder} тг")
            send_message(chat_id, '\n'.join(report_lines))
            users_state.pop(chat_id)
        else:
            if ':' in text:
                parts = text.split(':', 1)
                desc = parts[0].strip()
                amount_str = parts[1].strip().replace('тг', '').strip()
                if amount_str.isdigit():
                    amount = int(amount_str)
                    data['expenses'].append((desc, amount))
                    send_message(chat_id, f"Добавлено: {desc} — {amount} тг\nВведите следующую затрату или 'готово' для завершения.")
                else:
                    send_message(chat_id, "Сумма должна быть числом. Попробуйте снова.")
            else:
                send_message(chat_id, "Неправильный формат. Используйте 'Описание: сумма'.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
