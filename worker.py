import os, requests, datetime
import pandas as pd
from datetime import timedelta, timezone

NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")
SHEET_URL = os.getenv("SHEET_CSV_URL") # Ссылка на CSV версию листа Queue
EVENT_ID = os.getenv("EVENT_ID")

def get_moscow_now():
    return datetime.datetime.now(timezone(timedelta(hours=3)))

def get_target_date():
    now = get_moscow_now()
    days_ahead = (5 - now.weekday() + 7) % 7
    if days_ahead == 0 and now.hour >= 11:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.strftime("%d.%m.%Y")

def get_sync_boundary():
    now = get_moscow_now()
    days_since_sat = (now.weekday() - 5) % 7
    last_sat = now - timedelta(days=days_since_sat)
    boundary = last_sat.replace(hour=11, minute=0, second=0, microsecond=0)
    if now.weekday() == 5 and now.hour < 11:
        boundary -= timedelta(days=7)
    return boundary

def get_token():
    u = NRMS_USER if NRMS_USER.startswith('A') else 'A'+NRMS_USER
    r = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                      json={"username": u, "password": NRMS_PASS})
    return r.json()['result']['token']

def run_sync():
    target_date = get_target_date()
    boundary_time = get_sync_boundary()
    
    try:
        token = get_token()
    except: return

    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        msk_tz = timezone(timedelta(hours=3))
        df.iloc[:, 5] = pd.to_datetime(df.iloc[:, 5]).dt.tz_localize(msk_tz, ambiguous='infer')
        active_vols_df = df[df.iloc[:, 5] > boundary_time].copy()

        volunteers_payload = []
        for _, row in active_vols_df.iterrows():
            volunteers_payload.append({
                "verst_id": int(row.iloc[0]),
                "role_id": int(row.iloc[1])
            })

        payload = {
            "event_id": int(EVENT_ID),
            "date": target_date,
            "upload_status_id": 1,
            "volunteers": volunteers_payload
        }
        
        requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", 
                             json=payload, headers=headers)
    except Exception as e:
        print(f"Sync error: {e}")

if __name__ == "__main__":
    run_sync()
