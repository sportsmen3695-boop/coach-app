import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Меняем версию файла на v10, чтобы начать без конфликтов типов от прошлых ошибок
DB_FILE = 'students_v10.csv'

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    
    # Считываем данные, принудительно указывая, что телефон и родитель — это текст
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    
    # Обрабатываем даты ТОЛЬКО если таблица не пустая, иначе будет ошибка
    if not df.empty:
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- МОБИЛЬНЫЙ ТЕМНЫЙ ДИЗАЙН ---
st.set_page_config(page_title="Coach Pro", page_icon="🥋", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #0f172a; color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    .stButton>button { width: 100%; height: 50px; border-radius: 12px; font-weight: bold; }
    div[data-testid="stVerticalBlock"] > div > div > [data-testid="stVerticalBlock"] {
        background: rgba(30, 41, 59, 0.7);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #334155;
    }
    </style>
    """, unsafe_allow_html=True)

df = load_data()

# --- ПАНЕЛЬ ЗАДАЧ (ИСПРАВЛЕНО) ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    # Безопасный подсчет должников
    if not df.empty:
        # Отбрасываем пустые даты перед сравнением, чтобы избежать TypeError
        valid_dates = df.dropna(subset=['Оплачено до'])
        debtors = len(valid_dates[valid_dates['Оплачено до'] < date.today()])
        
        if debtors > 0:
            st.error(f"🔴 Должников: {debtors}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Список группы")
    if not df.empty:
        search = st.text_input("🔍 Поиск", placeholder="Имя ученика...")
        view_df = df.copy()
        
        if search:
            # Добавлено astype(str) для защиты от ошибок поиска
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search, case=False, na=False)]
        
        view_df.index = range(1, len(view_df) + 1)
        
        # Исправлена логика подсветки должников (защита от пустых дат)
        def style_debtors(row):
            is_debt = pd.notna(row['Оплачено до']) and row['Оплачено до'] < date.today()
            return ['background-color: rgba(248, 113, 113, 0.2)' if is_debt else '' for _ in row]

        st.dataframe(view_df.style.apply(style_debtors, axis=1), use_container_width=True)
    else:
        st.info("База пуста. Перейдите в раздел 'Регистрация'.")

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
            # БЕЗОПАСНАЯ ПРОВЕРКА НА ДУБЛИКАТ
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
        # Сортировка имен по алфавиту для удобства
        sorted_names = sorted(df['Имя ученика'].astype(str).unique())
        student = st.selectbox("Выбор ученика", sorted_names)
        new_paid = st.date_input("Продлить до", value=get_end_of_month(date.today()))
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Оплачено"):
            idx = df[df['Имя ученика'] == student].index[0]
            df.at[idx, 'Оплачено до'] = new_paid
            save_data(df)
            st.rerun()
        
        if c2.button("🗑 Удалить"):
            df = df[df['Имя ученика'] != student]
            save_data(df)
            st.rerun()
    else:
        st.info("Нет учеников для управления.")
