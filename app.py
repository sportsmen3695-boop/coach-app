import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Новая версия файла, чтобы избежать конфликтов со старыми колонками
DB_FILE = 'students_v4.csv'

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
    
    df = pd.read_csv(DB_FILE)
    # Гарантируем, что даты — это строки для стабильности
    df['Оплачено до'] = df['Оплачено до'].astype(str)
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

st.set_page_config(page_title="Менеджер Группы", page_icon="🥋", layout="wide")
st.title("🥋 Управление учениками и Оплатой")

df = load_data()

tab1, tab2 = st.tabs(["➕ Редактирование и Оплата", "📊 База учеников"])

# --- ВКЛАДКА 1: УПРАВЛЕНИЕ ---
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🆕 Добавить ученика")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("ФИО ученика (полностью)")
            dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            parent = st.text_input("Инициалы/ФИО родителя")
            phone = st.text_input("Номер телефона")
            paid_until = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            
            if st.form_submit_button("Создать карточку"):
                name = name.strip()
                if not name:
                    st.error("Ошибка: Имя ученика не может быть пустым!")
                elif name in df['Имя ученика'].values:
                    st.error(f"Ошибка: Ученик с именем '{name}' уже есть в базе!")
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
                    st.success(f"Ученик {name} добавлен!")
                    st.rerun()

    with col2:
        st.subheader("💰 Прием оплаты")
        if not df.empty:
            with st.form("payment_form"):
                # Сортируем список имен по алфавиту для удобства поиска
                student_list = sorted(df['Имя ученика'].tolist())
                selected_student = st.selectbox("Выберите ученика", student_list)
                
                new_expiry = st.date_input("Продлить абонемент до", value=get_end_of_month(date.today()))
                
                if st.form_submit_button("Подтвердить оплату"):
                    idx = df.index[df['Имя ученика'] == selected_student].tolist()[0]
                    df.at[idx, 'Оплачено до'] = new_expiry.isoformat()
                    save_data(df)
                    st.success(f"Оплата для {selected_student} сохранена!")
                    st.rerun()
                    
            st.divider()
            st.subheader("🗑 Удаление")
            student_to_del = st.selectbox("Удалить ученика из базы", ["-- выберите --"] + student_list)
            if st.button("❌ Удалить безвозвратно", type="secondary"):
                if student_to_del != "-- выберите --":
                    df = df[df['Имя ученика'] != student_to_del]
                    save_data(df)
                    st.warning(f"Ученик {student_to_del} удален.")
                    st.rerun()
        else:
            st.info("База пока пуста. Добавьте первого ученика слева.")

# --- ВКЛАДКА 2: БАЗА ДАННЫХ ---
with tab2:
    st.header("Список группы")
    
    if not df.empty:
        # Панель инструментов над таблицей
        search_query = st.text_input("🔍 Быстрый поиск по имени", "").lower()
        
        # Фильтруем данные по поиску
        filtered_df = df[df['Имя ученика'].str.lower().str.contains(search_query, na=False)]
        
        # Функция для раскраски строк
        def style_rows(row):
            expiry = pd.to_datetime(row['Оплачено до']).date()
            if expiry < date.today():
                return ['background-color: #ffcccc'] * len(row) # Красный - долг
            return [''] * len(row)

        # Вывод таблицы
        st.dataframe(
            filtered_df.style.apply(style_rows, axis=1),
            use_container_width=True,
            column_config={
                "Телефон": st.column_config.TextColumn("📞 Телефон"),
                "Оплачено до": st.column_config.DateColumn("📅 Оплачено до"),
                "Дата рождения": st.column_config.DateColumn("🎂 ДР")
            }
        )
        
        st.write(f"**Всего в группе:** {len(df)} чел. | **Найдено:** {len(filtered_df)}")
        
        # Кнопка экспорта
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Скачать всю базу в Excel (CSV)", csv, "base_coaching.csv", "text/csv")
    else:
        st.info("Здесь будет отображаться список вашей группы после добавления учеников.")
