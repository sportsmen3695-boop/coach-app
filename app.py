import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Файл базы данных
DB_FILE = 'students_v7.csv'

# --- ЛОГИКА ---
def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE)
    df['Оплачено до'] = pd.to_datetime(df['Оплачено до']).dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения']).dt.date
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- ДИЗАЙН (ГЛОБАЛЬНОЕ ИСПРАВЛЕНИЕ ФОНА) ---
st.set_page_config(page_title="Coach CRM Pro", page_icon="🥋", layout="wide")

st.markdown("""
    <style>
    /* 1. Глобальный фон приложения */
    .stApp {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: #f8fafc;
    }

    /* 2. Стилизация бокового меню */
    [data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155;
    }

    /* 3. Карточки (контейнеры для форм и таблиц) */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlock"] {
        background: rgba(30, 41, 59, 0.7);
        padding: 25px;
        border-radius: 16px;
        border: 1px solid #334155;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
    }

    /* 4. Поля ввода */
    input, select, textarea {
        background-color: #0f172a !important;
        color: white !important;
        border: 1px solid #475569 !important;
    }

    /* 5. Метрики */
    [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-weight: bold;
    }
    
    /* 6. Таблица */
    .stDataFrame {
        background: #1e293b;
        border-radius: 10px;
    }

    /* Заголовки */
    h1, h2, h3 {
        color: #f1f5f9 !important;
        letter-spacing: -0.025em;
    }

    /* Кнопки */
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

df = load_data()

# --- СТРУКТУРА ПРИЛОЖЕНИЯ ---
with st.sidebar:
    st.title("🥋 COACH PRO")
    page = st.radio("Навигация", ["📊 Дашборд", "➕ Регистрация", "⚙️ Управление"])
    st.divider()
    if not df.empty:
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("💾 Экспорт базы", csv, "students.csv", "text/csv", use_container_width=True)

# --- СТРАНИЦА: ДАШБОРД ---
if page == "📊 Дашборд":
    st.title("Состояние группы")
    
    if not df.empty:
        today = date.today()
        debtors = df[df['Оплачено до'] < today]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Всего", len(df))
        m2.metric("Активны", len(df) - len(debtors))
        m3.metric("Должники", len(debtors), delta=f"-{len(debtors)}", delta_color="inverse")
        
        st.subheader("📋 Список учеников")
        search = st.text_input("🔍 Поиск по ФИО", placeholder="Введите фамилию...")
        
        view_df = df.copy()
        if search:
            view_df = view_df[view_df['Имя ученика'].str.contains(search, case=False, na=False)]
        
        # Индексация с 1
        view_df.index = range(1, len(view_df) + 1)
        
        # Подсветка должников в таблице
        def style_rows(row):
            if row['Оплачено до'] < today:
                return ['background-color: rgba(220, 38, 38, 0.2); color: #fca5a5'] * len(row)
            return [''] * len(row)

        st.dataframe(
            view_df.style.apply(style_rows, axis=1),
            use_container_width=True,
            column_config={
                "Оплачено до": st.column_config.DateColumn("📅 Срок оплаты"),
                "Дата рождения": st.column_config.DateColumn("🎂 ДР"),
                "Телефон": st.column_config.TextColumn("📞 Контакт")
            }
        )
    else:
        st.info("База пуста. Добавьте первого ученика в меню 'Регистрация'.")

# --- СТРАНИЦА: РЕГИСТРАЦИЯ ---
elif page == "➕ Регистрация":
    st.title("Новая карточка")
    with st.container():
        with st.form("add_student"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("ФИО ученика*")
                dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            with c2:
                parent = st.text_input("Родитель")
                phone = st.text_input("Телефон")
            
            paid_until = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            
            if st.form_submit_button("Добавить в систему", use_container_width=True):
                if name.strip():
                    new_student = pd.DataFrame([{
                        'Имя ученика': name.strip(),
                        'Дата рождения': dob,
                        'ФИО родителя': parent.strip(),
                        'Телефон': phone.strip(),
                        'Оплачено до': paid_until
                    }])
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {name} добавлен!")
                    st.rerun()
                else:
                    st.error("Поле 'Имя ученика' обязательно!")

# --- СТРАНИЦА: УПРАВЛЕНИЕ ---
elif page == "⚙️ Управление":
    st.title("Оплата и редактирование")
    if not df.empty:
        col_pay, col_del = st.columns(2)
        
        with col_pay:
            st.subheader("💳 Принять оплату")
            student_choice = st.selectbox("Ученик", sorted(df['Имя ученика'].unique()))
            new_expiry = st.date_input("Продлить до", value=get_end_of_month(date.today()))
            if st.button("Обновить абонемент", use_container_width=True):
                idx = df[df['Имя ученика'] == student_choice].index[0]
                df.at[idx, 'Оплачено до'] = new_expiry
                save_data(df)
                st.success(f"Абонемент {student_choice} обновлен!")
                st.rerun()
        
        with col_del:
            st.subheader("🗑 Удаление")
            to_delete = st.selectbox("Удалить ученика", ["-- Выберите --"] + sorted(df['Имя ученика'].tolist()))
            if st.button("⚠️ Подтвердить удаление", type="primary", use_container_width=True):
                if to_delete != "-- Выберите --":
                    df = df[df['Имя ученика'] != to_delete]
                    save_data(df)
                    st.warning(f"{to_delete} удален из базы.")
                    st.rerun()
    else:
        st.info("Данных для управления нет.")
