import os
import requests
import random
import sys
import time
from datetime import datetime, timedelta, timezone

# --- НАСТРОЙКИ (Берутся из GitHub Secrets автоматически) ---
VK_TOKEN = os.getenv('VK_TOKEN')
CHAT_IDS_RAW = os.getenv('VK_CHAT_IDS', '')
VK_GROUP_ID = os.getenv('VK_GROUP_ID') 
LAT = float(os.getenv('PARK_LAT', '55.75')) # Широта парка (по умолчанию Москва)
LON = float(os.getenv('PARK_LON', '37.61')) # Долгота парка
PARK_NAME = os.getenv('PARK_NAME', '5 вёрст')

try:
    CHAT_IDS = [int(i.strip()) for i in CHAT_IDS_RAW.split(',') if i.strip()]
except Exception as e:
    print(f"Ошибка парсинга CHAT_IDS: {e}")
    sys.exit(1)

def get_moscow_now():
    return datetime.now(timezone(timedelta(hours=3)))

def get_weather():
    # Запрашиваем прогноз погоды именно для координат этого парка
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe%2FMoscow&forecast_days=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Индекс 9 соответствует 09:00 утра
        temp = data['hourly']['temperature_2m'][9]
        prob = data['hourly']['precipitation_probability'][9]
        code = data['hourly']['weathercode'][9]
        
        weather_map = {
            0: "Ясно ☀️", 1: "Преимущественно ясно 🌤", 2: "Переменная облачность ⛅", 
            3: "Пасмурно ☁️", 45: "Туман 🌫️", 51: "Морось 🌧️", 61: "Небольшой дождь 🌦️", 
            63: "Дождь ☔", 71: "Небольшой снег ❄️", 73: "Снегопад 🌨️", 80: "Ливневый дождь ⛈️"
        }
        status = weather_map.get(code, "Облачно ☁️")
        
        return (f"🌳 ПОГОДА В ЛОКАЦИИ {PARK_NAME.upper()} НА СТАРТЕ В 09:00:\n\n"
                f"🌡 Температура: {temp}°C\n"
                f"☁ На улице: {status}\n"
                f"☔ Вероятность осадков: {prob}%\n\n"
                f"Одевайтесь по погоде и до встречи! 🧡")
    except Exception as e:
        print(f"Ошибка получения погоды: {e}")
        return None

def get_all_potential_birthdays():
    now = get_moscow_now()
    today_str = now.strftime("%d.%m")
    all_users = {}

    # 1. Получаем именинников из группы
    try:
        res = requests.get("https://api.vk.com/method/groups.getMembers", params={
            "group_id": VK_GROUP_ID, "fields": "bdate", "count": 1000,
            "access_token": VK_TOKEN, "v": "5.131"
        }).json()
        for u in res.get('response', {}).get('items', []):
            all_users[u['id']] = u
    except Exception as e:
        print(f"Ошибка получения членов группы: {e}")

    # 2. Из чатов (если бот там админ)
    for chat_id in CHAT_IDS:
        try:
            res = requests.get("https://api.vk.com/method/messages.getConversationMembers", params={
                "peer_id": chat_id, "fields": "bdate", "access_token": VK_TOKEN, "v": "5.131"
            }).json()
            for u in res.get('response', {}).get('profiles', []):
                all_users[u['id']] = u
        except Exception as e:
            print(f"Ошибка получения членов чата {chat_id}: {e}")

    celebrants = []
    for u_id, u in all_users.items():
        bdate = u.get('bdate', '')
        if bdate:
            parts = bdate.split('.')
            if len(parts) >= 2:
                if f"{int(parts[0]):02d}.{int(parts[1]):02d}" == today_str:
                    name = f"{u.get('first_name')} {u.get('last_name')}"
                    celebrants.append(f"[id{u_id}|{name}]")

    if celebrants:
        names = ", ".join(list(set(celebrants)))
        return (f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\n"
                f"Сегодня в сообществе {PARK_NAME} праздник у: {names}! 🎉🧡\n"
                f"Желаем лёгких ног, ярких стартов и отличного настроения!")
    return None

def send_vk_message(peer_id, text):
    try:
        requests.post("https://api.vk.com/method/messages.send", data={
            "access_token": VK_TOKEN, "peer_id": peer_id, "message": text, 
            "random_id": random.randint(1, 2147483647), "v": "5.131"
        })
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

if __name__ == "__main__":
    now_msk = get_moscow_now()
    print(f"Запуск бота для {PARK_NAME}. Время МСК: {now_msk}")

    # 1. Погода (только по субботам)
    if now_msk.weekday() == 5:
        text_weather = get_weather()
        if text_weather:
            for chat in CHAT_IDS:
                send_vk_message(chat, text_weather)
    
    # 2. Дни рождения (каждый день)
    text_bd = get_all_potential_birthdays()
    if text_bd:
        for chat in CHAT_IDS:
            send_vk_message(chat, text_bd)
    else:
        print("Именинников сегодня нет.")
