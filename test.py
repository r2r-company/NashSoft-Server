import threading
import requests
import json

API_URL = "http://localhost:8000/api/document/"

HEADERS = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer ..."  # якщо потрібно
}

# 🔥 Тіло запиту для документа реалізації
PAYLOAD = {
    "doc_type": "sale",
    "company": 1,
    "warehouse": 1,
    "items": [
        {
            "product": 1,
            "quantity": 1
            # Ціну не передаємо — хай тягне з ціноутворення
        }
    ]
}

def send_request(index):
    response = requests.post(API_URL, headers=HEADERS, data=json.dumps(PAYLOAD))
    print(f"[{index}] Status: {response.status_code} → {response.text}")

def run_concurrent_requests(count=2):
    threads = []
    for i in range(count):
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

# 🔫 Запуск
if __name__ == "__main__":
    run_concurrent_requests(count=2)  # змінюй count як хочеш
