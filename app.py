import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os
import uuid

# Версия v14 - Финальная: исправлена нумерация, поиск и синтаксис
DB_FILE = 'students_v14.csv'
PAYMENTS_FILE = 'payments_v14.csv'
PRICE = 2500  
PERCENT_DIR = 0.40  

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

# --- ИНТЕРФЕЙС ---
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

# Расчет должников для сайдбара
debtors_count = 0
if not df_students.empty:
    valid_dates = pd.notna(df_students['Оплачено до'])
    debtors_count = (valid_dates & (df_students['Оплачено до'] < date.today())).sum()

# --- МЕНЮ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    if not df_students.empty:
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- СТРАНИЦА: ДАШБОРД ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    
    if not df_students.empty:
        today = date.today()
        
        # Финансы за текущий месяц
        collected_money = 0
        if not df_payments.empty:
            p_dates = pd.to_datetime
