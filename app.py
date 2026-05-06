import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Имя файла базы данных
DB_FILE = 'students_v5.csv'

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=[
            'Имя ученика', 
            'Дата рождения', 
            'ФИО родителя', 
            'Телефон', 
            'Оплачено до'
        ])
        df.to_csv(DB_FILE, index=False)
        return df
    
    df = pd.read_csv(DB_FILE)
    # Принудительное преобразование типов для стабильности
    df['Оплачено до'] = pd.to_datetime(df['Оплачено до']).dt.date.astype(str)
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения']).dt.date.astype(str)
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# Настройка страницы
st.set_page_config(page_title="Coach CRM", page_icon="🥋", layout="wide")

# Кастомный CSS для красоты
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stForm"] { border: none; background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_all_white_space=True)

st.title("🥋 Система управления секцией")

df = load_data()

# --- ВЕРХНЯЯ ПАНЕЛЬ МЕТРИК ---
if not df.empty:
    today = date.today()
    debtors_count = len(df[pd.to_datetime(df['Оплачено до']).dt.date < today])
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Всего учеников", len(df))
    m2.metric("Активны", len(df) - debtors_count)
    m3.metric("Должники", debtors_count, delta=f"-{debtors_count}", delta_color="inverse")

tab1, tab2 = st.tabs(["⚡ Управление", "📋 База и Отчетность"])

# --- ВКЛАДКА 1: УПРАВЛЕНИЕ ---
with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("👤 Новый ученик")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("ФИО ребенка")
            dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            parent = st.text_input("Контактное лицо (родитель)")
            phone = st.text_input("Телефон для связи")
            paid_until = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            
            submit = st.form_submit_button("✅ Добавить в базу", use_container_width=True)
            if submit:
                name = name.strip()
                if not name:
                    st.error("Введите имя ученика!")
                elif name in df['Имя ученика'].values:
                    st.error(f"Ученик '{name}' уже существует!")
                else:
                    new_entry = pd.DataFrame({
                        'Имя ученика': [name],
                        'Дата рождения': [dob.isoformat()],
                        'ФИО родителя': [parent.strip()],
                        'Телефон': [phone.strip()],
                        'Оплачено до': [paid_until.isoformat()]
                    })
                    df = pd.concat([df, new_entry], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {name} успешно добавлен!")
                    st.rerun()

    with col2:
        st.subheader("💳 Продление абонемента")
        if not df.empty:
            with st.form("payment_form"):
                student_list = sorted(df['Имя ученика'].tolist())
                selected_student = st.selectbox("Выберите ученика", student_list)
                new_expiry = st.date_input("Новая дата окончания", value=get_end_of_month(date.today()))
                
                if st.form_submit_button("💰 Записать оплату", use_container_width=True):
                    idx = df.index[df['Имя ученика'] == selected_student].tolist()[0]
                    df.at[idx, 'Оплачено до'] = new_expiry.isoformat()
                    save_data(df)
                    st.success(f"Абонемент для {selected_student} продлен!")
                    st.rerun()
            
            st.write("---")
            with st.expander("⚠️ Зона удаления"):
                student_to_del = st.selectbox("Кого удалить?", ["-- не выбрано --"] + student_list)
                if st.button("❌ Удалить из системы", type="primary", use_container_width=True):
                    if student_to_del != "-- не выбрано --":
                        df = df[df['Имя ученика'] != student_to_del]
                        save_data(df)
                        st.toast(f"Запись {student_to_del} удалена")
                        st.rerun()
        else:
            st.info("Добавьте учеников, чтобы принимать оплату.")

# --- ВКЛАДКА 2: БАЗА ДАННЫХ ---
with tab2:
    if not df.empty:
        # Поиск и фильтры
        search_col, _ = st.columns([2, 2])
        search_query = search_col.text_input("🔍 Поиск по ФИО", placeholder="Начните печатать...").lower()
        
        # Исправленная фильтрация
        filtered_df = df[df['Имя ученика'].str.lower().str.contains(search_query, na=False)].copy()
        
        # Настройка индекса с 1
        filtered_df.index = range(1, len(filtered_df) + 1)
        
        # Функция стиля
        def style_rows(row):
            expiry = pd.to_datetime(row['Оплачено до']).date()
            if expiry < date.today():
                return ['background-color: #ffe3e3; color: #910000'] * len(row)
            return [''] * len(row)

        # Отображение таблицы
        st.dataframe(
            filtered_df.style.apply(style_rows, axis=1),
            use_container_width=True,
            column_config={
                "Телефон": st.column_config.TextColumn("📞 Телефон"),
                "Оплачено до": st.column_config.DateColumn("📅 Оплата до"),
                "Дата рождения": st.column_config.DateColumn("🎂 ДР"),
                "Имя ученика": st.column_config.TextColumn("👤 Ученик", help="ФИО ребенка"),
            }
        )
        
        # Экспорт
        st.divider()
        csv_data = df.to_csv(index=False).encode('utf-8-sig') # utf-8-sig для Excel
        st.download_button(
            label="📥 Выгрузить базу в Excel (CSV)",
            data=csv_data,
            file_name=f"base_coaching_{date.today()}.csv",
            mime="text/csv",
        )
    else:
        st.info("База данных пуста.")
