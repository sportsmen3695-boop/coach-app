import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os
import uuid

# Версия v13 - транзакционная модель финансов и уникальные ID
DB_FILE = 'students_v13.csv'
PAYMENTS_FILE = 'payments_v13.csv'
PRICE = 2500  # Стоимость абонемента
PERCENT_DIR = 0.40  # Доля директора (40%)

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_students():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['ID', 'Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE, dtype={'ID': str, 'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    return df

def load_payments():
    if not os.path.exists(PAYMENTS_FILE):
        df = pd.DataFrame(columns=['Дата платежа', 'ID', 'Сумма'])
        df.to_csv(PAYMENTS_FILE, index=False)
        return df
    df = pd.read_csv(PAYMENTS_FILE, dtype={'ID': str})
    if not df.empty:
        df['Дата платежа'] = pd.to_datetime(df['Дата платежа'], errors='coerce').dt.date
        df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(0)
    return df

def save_data(df, file_name):
    df.to_csv(file_name, index=False)

# --- МОБИЛЬНЫЙ ТЕМНЫЙ ДИЗАЙН ---
st.set_page_config(page_title="Coach Finance Pro", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #0f172a; color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    .stMetric { background: rgba(30, 41, 59, 0.7); padding: 15px; border-radius: 12px; border: 1px solid #334155; }
    .stButton>button { width: 100%; height: 50px; border-radius: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

df_students = load_students()
df_payments = load_payments()

# Единая логика определения должников
debtors_mask = pd.Series(False, index=df_students.index)
if not df_students.empty:
    # Должники: дата оплаты в прошлом (пустые даты не учитываем)
    valid_dates = pd.notna(df_students['Оплачено до'])
    debtors_mask = valid_dates & (df_students['Оплачено до'] < date.today())
debtors_count = debtors_mask.sum()

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    if not df_students.empty:
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    
    if not df_students.empty:
        # --- ФИНАНСОВЫЕ РАСЧЕТЫ (ТРАНЗАКЦИОННЫЕ) ---
        today = date.today()
        
        # Считаем кассу только за ТЕКУЩИЙ месяц
        collected_money = 0
        if not df_payments.empty:
            current_month_payments = df_payments[
                (pd.to_datetime(df_payments['Дата платежа']).dt.month == today.month) &
                (pd.to_datetime(df_payments['Дата платежа']).dt.year == today.year)
            ]
            collected_money = current_month_payments['Сумма'].sum()
        
        # Потенциальный долг (сколько еще должны донести)
        remaining_money = debtors_count * PRICE
        
        director_share = collected_money * PERCENT_DIR
        coach_income = collected_money - director_share

        st.caption(f"Статистика за {today.strftime('%m.%Y')}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Собрано в этом месяце", f"{int(collected_money)} ₽", delta=f"Ожидаем долг: {int(
