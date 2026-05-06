import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Файл базы данных
DB_FILE = 'students_v8.csv'

# --- ЛОГИКА БЕЗОПАСНОСТИ ---
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

# --- УЛЬТРА-ТЕМНЫЙ МОБИЛЬНЫЙ ДИЗАЙН ---
st.set_page_config(page_title="Coach App", page_icon="🥋", layout="wide")

st.markdown("""
    <style>
    /* Глобальные настройки для мобильных */
    .stApp {
        background: #0f172a;
        color: #e2e8f0;
    }
    
    /* Скрытие лишних элементов Streamlit для чистоты */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Стиль карточек-контейнеров */
    [data-testid="stVerticalBlock"] > div > div > [data-testid="stVerticalBlock"] {
        background: #1e293b;
        border-radius: 12px;
        padding: 15px !important;
        border: 1px solid #334155;
        margin-bottom: 10px;
    }

    /* Адаптация кнопок под палец (больше высота) */
    .stButton>button {
        width: 100%;
        height: 50px;
        border-radius: 10px;
        background: #3b82f6;
        font-size: 16px;
        font-weight: 600;
    }

    /* Настройка боковой панели */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        width: 250px !important;
    }

    /* Заголовки */
    h1 { font-size: 1.8rem !important; padding-bottom: 10px; }
    h3 { font-size: 1.2rem !important; }

    /* Поля ввода */
    .stTextInput input, .stDateInput input, .stSelectbox div {
        background-color: #0f172a !important;
        border-radius: 8px !important;
        height: 45px !important;
    }
    </style>
    """, unsafe_allow_html=True)

df = load_data()

# --- ПАНЕЛЬ ЗАДАЧ (БОКОВАЯ) ---
with st.sidebar:
    st.markdown("## 🥋 Управление")
    page = st.radio("", ["📱 Главная", "👤 Новый ученик", "💳 Оплата"], label_visibility="collapsed")
    st.divider()
    
    # Метрика в сайдбаре для быстрого чека
    if not df.empty:
        debtors_count = len(df[df['Оплачено до'] < date.today()])
        st.error(f"Должников: {debtors_count}") if debtors_count > 0 else st.success("Долгов нет")

# --- СТРАНИЦА: ГЛАВНАЯ (ОПТИМИЗИРОВАННАЯ ТАБЛИЦА) ---
if page == "📱 Главная":
    st.title("Список группы")
    
    if not df.empty:
        search = st.text_input("🔍 Поиск...", placeholder="Имя ребенка")
        
        filtered = df.copy()
        if search:
            filtered = filtered[filtered['Имя ученика'].str.contains(search, case=False, na=False)]
        
        filtered = filtered.sort_values('Оплачено до')
        filtered.index = range(1, len(filtered) + 1)

        # Функция цветового выделения
        def highlight_mobile(row):
            if row['Оплачено до'] < date.today():
                return ['color: #ef4444; font-weight: bold'] * len(row)
            return [''] * len(row)

        st.dataframe(
            filtered.style.apply(highlight_mobile, axis=1),
            use_container_width=True,
            column_config={
                "Имя ученика": st.column_config.TextColumn("Ученик"),
                "Оплачено до": st.column_config.DateColumn("Оплата"),
                "Телефон": st.column_config.TextColumn("📞"),
                "Дата рождения": None, # Скрываем лишнее на главной для мобильных
                "ФИО родителя": None
            }
        )
    else:
        st.info("База пуста")

# --- СТРАНИЦА: РЕГИСТРАЦИЯ (ЗАПРЕТ ДУБЛЕЙ) ---
elif page == "👤 Новый ученик":
    st.title("Добавить ученика")
    with st.form("mobile_add"):
        name = st.text_input("ФИО ученика (полностью)*")
        dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
        parent = st.text_input("Имя родителя")
        phone = st.text_input("Телефон")
        paid = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
        
        submit = st.form_submit_button("СОЗДАТЬ")
        
        if submit:
            clean_name = name.strip()
            if not clean_name:
                st.warning("Введите имя!")
            # ПРОВЕРКА НА ДУБЛИКАТ
            elif clean_name.lower() in df['Имя ученика'].str.lower().values:
                st.error(f"Ошибка! Ученик '{clean_name}' уже есть в базе.")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': clean_name,
                    'Дата рождения': dob,
                    'ФИО родителя': parent.strip(),
                    'Телефон': phone.strip(),
                    'Оплачено до': paid
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_data(df)
                st.success("Добавлен!")
                st.rerun()

# --- СТРАНИЦА: ОПЛАТА (УДОБНО ДЛЯ СМАРТФОНА) ---
elif page == "💳 Оплата":
    st.title("Прием оплаты")
    if not df.empty:
        student = st.selectbox("Кто платит?", sorted(df['Имя ученика'].unique()))
        new_date = st.date_input("Продлить до", value=get_end_of_month(date.today()))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Оплачено"):
                idx = df[df['Имя ученика'] == student].index[0]
                df.at[idx, 'Оплачено до'] = new_date
                save_data(df)
                st.toast(f"Оплата принята для {student}")
                st.rerun()
        
        with col2:
            # Кнопка удаления вынесена отдельно для безопасности
            with st.expander("🗑 Удалить"):
                if st.button("Подтвердить"):
                    df = df[df['Имя ученика'] != student]
                    save_data(df)
                    st.rerun()
    else:
        st.info("Нет данных")
