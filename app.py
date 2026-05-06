import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Имя файла - меняем на v3, чтобы начать с чистого листа без старых ошибок типов
DB_FILE = 'students_v3.csv'

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
            'Оплачено до', 
            'Посещения'
        ])
        df.to_csv(DB_FILE, index=False)
    
    df = pd.read_csv(DB_FILE)
    df['Посещения'] = df['Посещения'].fillna('') 
    # Принудительно делаем колонку с оплатой текстовой, чтобы избежать TypeError
    df['Оплачено до'] = df['Оплачено до'].astype(str)
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

st.set_page_config(page_title="Трекер тренера", page_icon="🥋", layout="wide")
st.title("🥋 Журнал тренера: Посещаемость и Оплата")

df = load_data()

tab1, tab2, tab3 = st.tabs(["📋 Посещаемость", "➕ Ученики и Оплата", "📊 База данных"])

# --- ВКЛАДКА 1: ПОСЕЩАЕМОСТЬ ---
with tab1:
    st.header("Отметка посещаемости")
    today = st.date_input("Дата тренировки", date.today())

    if df.empty:
        st.warning("База пуста.")
    else:
        with st.form("attendance_form"):
            present_students = []
            for index, row in df.iterrows():
                # Превращаем текст из базы обратно в дату для сравнения
                paid_until = pd.to_datetime(row['Оплачено до']).date()
                if today > paid_until:
                    warning = " 🔴 (ДОЛГ!)"
                else:
                    warning = f" 🟢 (до {paid_until.strftime('%d.%m')})"
                    
                is_present = st.checkbox(f"{row['Имя ученика']}{warning}", key=f"check_{index}")
                if is_present:
                    present_students.append(index)
            
            if st.form_submit_button("Сохранить посещаемость"):
                date_str = today.strftime('%d.%m')
                for idx in present_students:
                    current = str(df.at[idx, 'Посещения'])
                    df.at[idx, 'Посещения'] = date_str if current == '' else current + f", {date_str}"
                save_data(df)
                st.success("Сохранено!")
                st.rerun()

# --- ВКЛАДКА 2: УПРАВЛЕНИЕ ---
with tab2:
    st.header("Управление")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Новый ученик")
        with st.form("add_form"):
            new_name = st.text_input("ФИО ученика")
            new_dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            new_parent = st.text_input("ФИО родителя")
            new_phone = st.text_input("Телефон")
            new_paid = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            
            if st.form_submit_button("Добавить"):
                if new_name:
                    new_student = pd.DataFrame({
                        'Имя ученика': [new_name],
                        # Сохраняем даты как текст (строки)
                        'Дата рождения': [new_dob.isoformat()],
                        'ФИО родителя': [new_parent],
                        'Телефон': [new_phone],
                        'Оплачено до': [new_paid.isoformat()],
                        'Посещения': ['']
                    })
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success("Добавлен!")
                    st.rerun()

    with col2:
        st.subheader("Оплата")
        if not df.empty:
            with st.form("renew_form"):
                student = st.selectbox("Ученик", df['Имя ученика'])
                new_date_paid = st.date_input("Продлить до", value=get_end_of_month(date.today()))
                clear_v = st.checkbox("Очистить посещения")
                
                if st.form_submit_button("Сохранить оплату"):
                    idx = df.index[df['Имя ученика'] == student].tolist()[0]
                    # ВАЖНО: сохраняем дату как строку через .isoformat()
                    df.at[idx, 'Оплачено до'] = new_date_paid.isoformat()
                    if clear_v:
                        df.at[idx, 'Посещения'] = ''
                    save_data(df)
                    st.success("Оплата принята!")
                    st.rerun()

# --- ВКЛАДКА 3: БАЗА ---
with tab3:
    st.header("База данных")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.download_button("Скачать CSV", df.to_csv(index=False).encode('utf-8'), "base.csv")
