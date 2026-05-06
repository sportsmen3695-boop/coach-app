import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Файл базы данных
DB_FILE = 'students_v6.csv'

# --- ФУНКЦИИ ЛОГИКИ ---
def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    
    df = pd.read_csv(DB_FILE)
    # Гарантируем корректный формат дат для работы виджетов
    df['Оплачено до'] = pd.to_datetime(df['Оплачено до']).dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения']).dt.date
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="Coach Control", page_icon="🥋", layout="wide")

# Продвинутый CSS для стилизации
st.markdown("""
    <style>
    /* Фон всей страницы */
    .stApp { background-color: #f0f2f6; }
    
    /* Стилизация карточек (контейнеров) */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlock"] {
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    
    /* Заголовки */
    h1, h2, h3 { color: #1e293b; font-family: 'Inter', sans-serif; }
    
    /* Красивые кнопки */
    .stButton>button {
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

df = load_data()

# --- БОКОВАЯ ПАНЕЛЬ (НАВИГАЦИЯ) ---
with st.sidebar:
    st.title("🥋 Меню")
    page = st.radio("Перейти к:", ["📊 Дашборд и База", "➕ Добавить ученика", "💰 Оплата и Управление"])
    st.divider()
    st.info("Coach CRM v2.0\nСистема управления секцией")

# --- СТРАНИЦА 1: ДАШБОРД И БАЗА ---
if page == "📊 Дашборд и База":
    st.title("Список группы")
    
    # Метрики
    if not df.empty:
        today = date.today()
        debtors = df[df['Оплачено до'] < today]
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Всего в группе", len(df))
        with m2:
            st.metric("Активны", len(df) - len(debtors))
        with m3:
            st.metric("Должники", len(debtors), delta=f"-{len(debtors)}" if len(debtors) > 0 else 0, delta_color="inverse")
    
        st.divider()
        
        # Фильтрация и поиск
        c1, c2 = st.columns([2, 1])
        search = c1.text_input("🔍 Быстрый поиск по имени", placeholder="Введите имя...")
        
        filtered_df = df.copy()
        if search:
            filtered_df = filtered_df[filtered_df['Имя ученика'].str.contains(search, case=False, na=False)]
        
        # Сортировка по оплате (сначала те, у кого скоро кончается)
        filtered_df = filtered_df.sort_values('Оплачено до')
        
        # НАСТРОЙКА ИНДЕКСА С 1
        filtered_df.index = range(1, len(filtered_df) + 1)
        
        # Цветовая индикация строк
        def highlight_debt(row):
            return ['background-color: #fff1f0; color: #cf1322' if row['Оплачено до'] < date.today() else '' for _ in row]

        st.dataframe(
            filtered_df.style.apply(highlight_debt, axis=1),
            use_container_width=True,
            column_config={
                "Телефон": st.column_config.TextColumn("📞 Телефон"),
                "Оплачено до": st.column_config.DateColumn("📅 Оплата до"),
                "Дата рождения": st.column_config.DateColumn("🎂 ДР"),
                "Имя ученика": st.column_config.TextColumn("👤 Ученик"),
            }
        )
        
        # Экспорт
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать базу (CSV/Excel)", csv, "students_base.csv", "text/csv")
    else:
        st.info("База пока пуста. Перейдите в раздел 'Добавить ученика'.")

# --- СТРАНИЦА 2: ДОБАВЛЕНИЕ ---
elif page == "➕ Добавить ученика":
    st.title("Регистрация нового ученика")
    with st.container():
        with st.form("new_student"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("ФИО ученика*")
                dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            with c2:
                parent = st.text_input("ФИО родителя")
                phone = st.text_input("Телефон (номер)")
            
            paid_until = st.date_input("Начальная оплата до", value=get_end_of_month(date.today()))
            
            if st.form_submit_button("🔥 Создать карточку ученика", use_container_width=True):
                if not name.strip():
                    st.error("Имя обязательно!")
                else:
                    new_data = pd.DataFrame([{
                        'Имя ученика': name.strip(),
                        'Дата рождения': dob,
                        'ФИО родителя': parent.strip(),
                        'Телефон': phone.strip(),
                        'Оплачено до': paid_until
                    }])
                    df = pd.concat([df, new_data], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {name} добавлен!")
                    st.balloons()

# --- СТРАНИЦА 3: ОПЛАТА И УДАЛЕНИЕ ---
elif page == "💰 Оплата и Управление":
    st.title("Финансовые операции")
    
    if not df.empty:
        col_pay, col_del = st.columns(2)
        
        with col_pay:
            st.subheader("💳 Продлить абонемент")
            with st.form("pay_form"):
                student = st.selectbox("Выбрать из списка", sorted(df['Имя ученика'].tolist()))
                new_date = st.date_input("Новая дата окончания", value=get_end_of_month(date.today()))
                if st.form_submit_button("Подтвердить платеж", use_container_width=True):
                    idx = df[df['Имя ученика'] == student].index[0]
                    df.at[idx, 'Оплачено до'] = new_date
                    save_data(df)
                    st.success(f"Оплата для {student} принята!")
        
        with col_del:
            st.subheader("🗑 Удаление")
            student_to_del = st.selectbox("Кого исключить?", ["-- не выбрано --"] + sorted(df['Имя ученика'].tolist()))
            if st.button("Удалить безвозвратно", type="primary", use_container_width=True):
                if student_to_del != "-- не выбрано --":
                    df = df[df['Имя ученика'] != student_to_del]
                    save_data(df)
                    st.warning(f"Ученик {student_to_del} удален.")
                    st.rerun()
    else:
        st.info("Нет данных для управления.")
