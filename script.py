import os
import requests
import random
import pytz
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

SCRIPT_URL = os.getenv("SCRIPT_URL")
LOCATION_ID = os.getenv("LOCATION_ID")

def get_config():
    url = f"{SCRIPT_URL}?park={LOCATION_ID}&action=get_bot_config"
    return requests.get(url, timeout=15).json()

def get_detailed_results(loc_id, date_str):
    url_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    url = f"https://5verst.ru/{loc_id}/results/{url_date}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = {"count": 0, "url": url, "new_total": [], "new_location": [], "pbs": []}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200: return res
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.select_one(".results-table") or soup.find("table")
        if table:
            rows = table.find_all('tr')[1:]
            res["count"] = len(rows)
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 9: continue
                name = cols[1].get_text(strip=True).split('\n')[0]
                if cols[7].get_text(strip=True) == "1": res["new_total"].append(name)
                if "ЛР" in cols[9].get_text(strip=True): res["pbs"].append(name)
    except: pass
    return res

class NRMS_API:
    def __init__(self, user, pwd, event_id):
        self.base_url = "https://nrms.5verst.ru/api/v1"
        self.headers = {"Content-Type": "application/json"}
        self.user = user if user.startswith('A') else 'A'+user
        self.pwd = pwd
        self.event_id = event_id

    def login(self):
        try:
            r = requests.post(f"{self.base_url}/auth/login", json={"username": self.user, "password": self.pwd})
            token = r.json().get("result", {}).get("token")
            if token:
                self.headers["Authorization"] = f"Bearer {token}"
                return True
        except: return False
        return False

    def get_volunteers(self, date_str):
        try:
            f_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            r = requests.post(f"{self.base_url}/event/volunteer/list", 
                             json={"event_id": int(self.event_id), "event_date": f_date}, 
                             headers=self.headers)
            return r.json().get("result", {}).get("volunteer_list", [])
        except: return []

if __name__ == "__main__":
    conf = get_config()
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz)
    offset = (now.weekday() - 5) % 7
    last_sat_dt = now - timedelta(days=offset)
    date_str = last_sat_dt.strftime("%Y-%m-%d")
    
    results = get_detailed_results(LOCATION_ID, date_str)
    
    if results["count"] > 0:
        api = NRMS_API(conf['nrms_user'], conf['nrms_pass'], conf['event_id'])
        vols_text = ""
        if api.login():
            vList = api.get_volunteers(date_str)
            if vList:
                vols_text = "\n".join([f"• {v['full_name']} — {v['role_name']}" for v in vList])
        
        msg = f"🌳 Результаты {conf['park_name']}\n🗓 {last_sat_dt.strftime('%d.%m.%Y')}\n━━━━━━━━━━━━━━\n"
        msg += f"🏁 Финишировало: {results['count']}\n📊 Протокол: {results['url']}\n"
        if vols_text: msg += f"\n🍃 Волонтеры:\n{vols_text}"
        
        requests.post("https://api.vk.com/method/messages.send", data={
            "access_token": conf['vk_token'], "peer_id": conf['peer_id'], 
            "message": msg, "random_id": random.randint(1, 1e9), "v": "5.131"
        })
