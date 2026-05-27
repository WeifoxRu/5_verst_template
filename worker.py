import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

SCRIPT_URL = os.getenv("SCRIPT_URL")
LOCATION_ID = os.getenv("LOCATION_ID")

def get_config():
    url = f"{SCRIPT_URL}?park={LOCATION_ID}&action=get_bot_config"
    return requests.get(url, timeout=15).json()

def get_target_date():
    now = datetime.now(timezone(timedelta(hours=3)))
    days = (5 - now.weekday() + 7) % 7
    if days == 0 and now.hour >= 11: days = 7
    return (now + timedelta(days=days)).strftime("%d.%m.%Y")

def run_sync():
    conf = get_config()
    try:
        # Авторизация
        u = conf['nrms_user'] if conf['nrms_user'].startswith('A') else 'A'+conf['nrms_user']
        auth = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                            json={"username": u, "password": conf['nrms_pass']}).json()
        token = auth['result']['token']
        
        # Таблица
        df = pd.read_csv(conf['sheet_url'])
        vols = []
        for _, row in df.iterrows():
            if not pd.isna(row.iloc[0]):
                vols.append({"verst_id": int(row.iloc[0]), "role_id": int(row.iloc[1])})
        
        payload = {"event_id": int(conf['event_id']), "date": get_target_date(), "upload_status_id": 1, "volunteers": vols}
        requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", 
                     json=payload, headers={"Authorization": f"Bearer {token}"})
        print("Синхронизация успешна!")
    except Exception as e:
        print(f"Ошибка воркера: {e}")

if __name__ == "__main__":
    run_sync()
