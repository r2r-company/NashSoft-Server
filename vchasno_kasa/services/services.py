import requests

VCHASNO_API_URL = "http://localhost:3939"  # або свій локальний

def send_vchasno_task(task: int, idCashRegister: str, extra_data: dict = None):
    payload = {
        "task": task,
        "idCashRegister": idCashRegister
    }
    if extra_data:
        payload.update(extra_data)

    response = requests.post(VCHASNO_API_URL, json=payload)

    try:
        return response.json()
    except Exception:
        return {
            "status_code": response.status_code,
            "text": response.text
        }
