import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Версия v12 - исправлены ошибки в метриках и типах данных
DB_FILE = 'students_v12.csv'
PRICE = 2500  # Стоимость абонемента
PERCENT_DIR = 0.40  # Доля директора (40%)

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

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

df = load_data()

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    if not df.empty:
        valid_dates = df.dropna(subset=['Оплачено до'])
        # Очищаем от некорректных дат и считаем должников
        debtors_count = len(valid_dates[valid_dates['Оплачено до'] < date.today()])
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    
    if not df.empty:
        # --- ФИНАНСОВЫЕ РАСЧЕТЫ ---
        total_students = len(df)
        # Фильтруем тех, кто оплатил (дата оплаты >= сегодня)
        paid_students = len(df[df['Оплачено до'] >= date.today()])
        unpaid_students = total_students - paid_students
        
        collected_money = paid_students * PRICE
        remaining_money = unpaid_students * PRICE
        
        director_share = collected_money * PERCENT_DIR
        coach_income = collected_money - director_share

        # Вывод карточек (ИСПРАВЛЕНО: удалены лишние параметры)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Собрано (всего)", f"{collected_money} ₽", delta=f"Долг: {remaining_money} ₽", delta_color="inverse")
        with c2:
            st.metric("Доля директора (40%)", f"{int(director_share)} ₽")
        with c3:
            st.metric("Ваша чистая ЗП", f"{int(coach_income)} ₽")

        st.divider()
        
        # --- ТАБЛИЦА ---
        search = st.text_input("🔍 Быстрый поиск", placeholder="Имя ученика...")
        view_df = df.copy()
        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search, case=False, na=False)]
        
        view_df.index = range(1, len(view_df) + 1)
        
        def style_rows(row):
            is_debt = pd.notna(row['Оплачено до']) and row['Оплачено до'] < date.today()
            return ['background-color: rgba(248, 113, 113, 0.15); color: #fca5a5' if is_debt else '' for _ in row]

        st.dataframe(view_df.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("Добавьте учеников для расчета статистики.")

elif page == "➕ Регистрация":
    st.title("Новый ученик")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("ФИО ученика*").strip()
        dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
        parent = st.text_input("Родитель")
        phone = st.text_input("Телефон")
        paid = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
        
        if st.form_submit_button("СОХРАНИТЬ"):
            if not name:
                st.error("Введите имя!")
            elif not df.empty and name.lower() in df['Имя ученика'].astype(str).str.lower().values:
                st.warning(f"Ученик {name} уже есть в базе!")
            else:
                new_data = pd.DataFrame([{
                    'Имя ученика': name, 
                    'Дата рождения': dob, 
                    'ФИО родителя': parent, 
                    'Телефон': phone, 
                    'Оплачено до': paid
                }])
                df = pd.concat([df, new_data], ignore_index=True)
                save_data(df)
                st.success("Добавлено!")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление")
    if not df.empty:
        student = st.selectbox("Выбор ученика", sorted(df['Имя ученика'].astype(str).unique()))
        new_paid = st.date_input("Продлить до", value=get_end_of_month(date.today()))
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Подтвердить оплату"):
            idx = df[df['Имя ученика'] == student].index[0]
            df.at[idx, 'Оплачено до'] = new_paid
            save_data(df)
            st.success("Оплата сохранена")
            st.rerun()
        
        if c2.button("🗑 Удалить"):
            df = df[df['Имя ученика'] != student]
            save_data(df)
            st.rerun()
