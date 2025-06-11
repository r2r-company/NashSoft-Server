import streamlit as st
import requests
import pandas as pd
from datetime import date

# === Налаштування ===
API_BASE = "http://127.0.0.1:8000/api"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQ3Mzg0OTQ3LCJpYXQiOjE3NDY3ODAxNDcsImp0aSI6IjU2MjVjNzAwZDdmMDQ5NzY4OGFjOTQzYzc5ZGZiYjI0IiwidXNlcl9pZCI6Mn0.6P2HhhulR0SIrlhbQkZkHtJHJjr7OVmNp5rftiPKIzg"  # 🔐 Встав сюди актуальний токен
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

st.set_page_config(page_title="NashSoft Dashboard", layout="wide")
st.title("📦 NashSoft – Облік, Аналітика, Довідники")

# === Розділи ===
sections = {
    "Документи обліку": [
        ("Поступлення", "/documents/?type=receipt"),
        ("Реалізація", "/documents/?type=sale"),
        ("Повернення постачальнику", "/documents/?type=return_to_supplier"),
        ("Повернення від клієнта", "/documents/?type=return_from_client"),
        ("Переміщення", "/documents/?type=transfer"),
        ("Інвентаризація", "/documents/?type=inventory"),
        ("Оприбуткування", "/documents/?type=stock_in"),
    ],
    "Фінанси": [
        ("Грошові документи", "/money-documents/"),
        ("Грошові операції", "/money-operations/"),
        ("Проводки", "/money-ledger/"),
        ("Баланс кас/банку", "/money/balance/"),
        ("Бухгалтерський баланс рахунків", "/account-ledger-balance/"),
    ],
    "Аналітика": [
        ("Залишки по складах", "/stock/warehouses/"),
        ("Борги постачальникам", "/supplier-debts/"),
        ("Баланс постачальників", "/supplier-balance/"),
        ("Аналітика постачальника", "/supplier-payments/?supplier=1"),
        ("FIFO по товару", "/debug/operations/1/"),
        ("Звіт по ПДВ (рах. 644)", "/vat-report/"),
    ],
    "Ціноутворення": [
        ("Ціноутворення", "/price-setting-documents/"),
    ],
    "Довідники": [
        ("Товари", "/products/"),
        ("Групи товарів", "/product-groups/"),
        ("Постачальники", "/suppliers/"),
        ("Клієнти", "/customers/"),
        ("Склади", "/warehouses/"),
        ("Компанії", "/companies/"),
        ("Фірми", "/firms/"),
        ("Відділи", "/departments/"),
    ],
    "Звітність": [
        ("Реєстр податкових зобовʼязань", "/vat-obligation-report/"),
    ]
}

# === GET-запит
def fetch_data(endpoint):
    try:
        res = requests.get(f"{API_BASE}{endpoint}", headers=HEADERS)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        st.error(f"❌ Помилка при запиті {endpoint}:\n{e}")
        return []

# === Tabs для секцій
tabs = st.tabs(list(sections.keys()) + ["Калькуляція"])

# === Вивід секцій
for i, (section_title, items) in enumerate(sections.items()):
    with tabs[i]:
        for label, endpoint in items:
            st.subheader(label)

            if "vat-obligation-report" in endpoint:
                col1, col2 = st.columns(2)
                with col1:
                    start = st.date_input("Початок періоду", value=date.today().replace(day=1), key=f"{label}_start")
                with col2:
                    end = st.date_input("Кінець періоду", value=date.today(), key=f"{label}_end")
                full_endpoint = f"{endpoint}?start={start}&end={end}"
                data = fetch_data(full_endpoint)
            else:
                data = fetch_data(endpoint)

            if isinstance(data, list) and data:
                st.dataframe(pd.DataFrame(data))
            elif isinstance(data, dict) and data:
                st.json(data)
            else:
                st.info("🔍 Даних не знайдено.")

# === Калькуляція
with tabs[-1]:
    st.subheader("🧪 Калькуляція (техкарта)")
    with st.form("calc_form"):
        product_id = st.number_input("ID продукту", min_value=1, step=1)
        mode = st.selectbox("Режим", ["input", "output"])
        weight = st.number_input("Вага", min_value=0.01, value=1.0)
        submitted = st.form_submit_button("🔍 Розрахувати")

    if submitted:
        payload = {"product_id": product_id, "mode": mode, "weight": weight}
        try:
            res = requests.post(f"{API_BASE}/tech-calc/", json=payload, headers=HEADERS)
            res.raise_for_status()
            st.success("✅ Розрахунок виконано!")
            st.json(res.json())
        except Exception as e:
            st.error(f"❌ Помилка калькуляції:\n{e}")
