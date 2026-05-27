import os
import requests
import random
import sys
from datetime import datetime, timedelta, timezone

# Эти две переменные пропишет Фабрика в GitHub Actions или в файл окружения
# Мы берем их из переменных среды процесса
SCRIPT_URL = os.getenv("SCRIPT_URL")
LOCATION_ID = os.getenv("LOCATION_ID")

def get_config():
    """Запрашивает конфиг парка из Универсального Бэкенда"""
    if not SCRIPT_URL or not LOCATION_ID:
        print("Ошибка: SCRIPT_URL или LOCATION_ID не заданы!")
        sys.exit(1)
    
    url = f"{SCRIPT_URL}?park={LOCATION_ID}&action=get_bot_config"
    try:
        response = requests.get(url, timeout=15)
        return response.json()
    except Exception as e:
        print(f"Ошибка получения конфигурации: {e}")
        sys.exit(1)

def get_moscow_now():
    return datetime.now(timezone(timedelta(hours=3)))

def get_weather(lat=56.3269, lon=44.0059, park_name="5 вёрст"):
    """Запрашивает погоду для координат парка"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe%2FMoscow&forecast_days=1"
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
        
        return (f"🌳 ПОГОДА В ЛОКАЦИИ {park_name.upper()} НА СТАРТЕ В 09:00:\n\n"
                f"🌡 Температура: {temp}°C\n"
                f"☁ На улице: {status}\n"
                f"☔ Вероятность осадков: {prob}%\n\n"
                f"Одевайтесь по погоде и до встречи! 🧡")
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return None

def get_all_potential_birthdays(group_id, token, park_name, chat_ids):
    """Ищет именинников в группе и чатах"""
    now = get_moscow_now()
    today_str = now.strftime("%d.%m")
    all_users = {}

    # 1. Из группы
    try:
        res = requests.get("https://api.vk.com/method/groups.getMembers", params={
            "group_id": group_id, "fields": "bdate", "count": 1000,
            "access_token": token, "v": "5.131"
        }).json()
        if 'response' in res:
            for u in res['response'].get('items', []):
                all_users[u['id']] = u
    except: pass

    # 2. Из чатов
    for chat_id in chat_ids:
        try:
            res = requests.get("https://api.vk.com/method/messages.getConversationMembers", params={
                "peer_id": chat_id, "fields": "bdate", "access_token": token, "v": "5.131"
            }).json()
            if 'response' in res:
                for u in res['response'].get('profiles', []):
                    all_users[u['id']] = u
        except: pass

    celebrants = []
    for u_id, u in all_users.items():
        bdate = u.get('bdate', '')
        if bdate and bdate.startswith(today_str):
            name = f"{u.get('first_name')} {u.get('last_name')}"
            celebrants.append(f"[id{u_id}|{name}]")

    if celebrants:
        names = ", ".join(list(set(celebrants)))
        return (f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\n"
                f"Сегодня в сообществе {park_name} праздник у: {names}! 🎉🧡\n"
                f"Желаем лёгких ног, ярких стартов и отличного настроения!")
    return None

def send_vk_message(token, peer_id, text):
    try:
        requests.post("https://api.vk.com/method/messages.send", data={
            "access_token": token, "peer_id": peer_id, "message": text, 
            "random_id": random.randint(1, 2147483647), "v": "5.131"
        })
    except Exception as e:
        print(f"Ошибка отправки: {e}")

if __name__ == "__main__":
    # 1. Получаем секретные настройки из бэкенда
    conf = get_config()
    
    # Извлекаем данные
    TOKEN = conf.get('vk_token')
    PEER_ID = conf.get('peer_id')
    # Используем LOCATION_ID как group_id (обычно они совпадают в Registry)
    GROUP_ID = os.getenv("LOCATION_ID") 
    
    now_msk = get_moscow_now()
    print(f"Запуск бота. Время МСК: {now_msk}")

    # 2. Погода по субботам
    if now_msk.weekday() == 5:
        text_weather = get_weather(park_name=conf.get('park_name', '5 вёрст'))
        if text_weather:
            send_vk_message(TOKEN, PEER_ID, text_weather)
    
    # 3. Дни рождения
    text_bd = get_all_potential_birthdays(GROUP_ID, TOKEN, conf.get('park_name', '5 вёрст'), [PEER_ID])
    if text_bd:
        send_vk_message(TOKEN, PEER_ID, text_bd)
