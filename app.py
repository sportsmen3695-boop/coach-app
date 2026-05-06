import streamlit as st
import pandas as pd
from datetime import date
import os

# Имя файла для хранения базы данных
DB_FILE = 'students.csv'

# Функция для загрузки данных
def load_data():
    if not os.path.exists(DB_FILE):
        # Если файла нет, создаем пустой DataFrame
        df = pd.DataFrame(columns=['Имя', 'Дата рождения', 'Остаток занятий'])
        df.to_csv(DB_FILE, index=False)
    return pd.read_csv(DB_FILE)

# Функция для сохранения данных
def save_data(df):
    df.to_csv(DB_FILE, index=False)

# Настройка страницы
st.set_page_config(page_title="Трекер тренера", page_icon="🥋", layout="wide")
st.title("🥋 Журнал тренера: Посещаемость и Оплата")

# Загружаем базу при каждом обновлении страницы
df = load_data()

# Создаем интерфейс с вкладками
tab1, tab2, tab3 = st.tabs(["📋 Отметка посещаемости", "➕ Управление учениками", "📊 База данных"])

# --- ВКЛАДКА 1: ПОСЕЩАЕМОСТЬ ---
with tab1:
    st.header("Отметка посещаемости")
    today = st.date_input("Дата тренировки", date.today())

    if df.empty:
        st.warning("База учеников пуста. Добавьте учеников во вкладке 'Управление учениками'.")
    else:
        st.write("Отметьте тех, кто присутствует сегодня:")
        
        # Используем форму, чтобы данные не перезагружались при каждом клике
        with st.form("attendance_form"):
            present_students = []
            for index, row in df.iterrows():
                # Показываем предупреждение, если абонемент закончился
                if row['Остаток занятий'] <= 0:
                    warning = " 🔴 (Абонемент закончился!)"
                else:
                    warning = f" (Осталось: {row['Остаток занятий']})"
                    
                is_present = st.checkbox(f"{row['Имя']}{warning}", key=f"check_{index}")
                if is_present:
                    present_students.append(index)
            
            submitted = st.form_submit_button("Сохранить посещаемость")
            
            if submitted:
                if not present_students:
                    st.info("Никто не отмечен.")
                else:
                    # Списываем по одному занятию у присутствующих
                    for idx in present_students:
                        df.at[idx, 'Остаток занятий'] -= 1
                    save_data(df)
                    st.success(f"Посещаемость за {today} сохранена! Списано занятий у {len(present_students)} учеников.")
                    st.rerun() # Перезагружаем страницу для обновления цифр

# --- ВКЛАДКА 2: УПРАВЛЕНИЕ УЧЕНИКАМИ ---
with tab2:
    st.header("Управление учениками")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Добавить нового ученика")
        with st.form("add_student_form"):
            new_name = st.text_input("ФИО ученика")
            new_dob = st.date_input("Дата рождения", min_value=date(1950, 1, 1), max_value=date.today())
            new_classes = st.number_input("Количество оплаченных занятий", min_value=0, value=12)
            
            if st.form_submit_button("Добавить"):
                if new_name:
                    new_student = pd.DataFrame({
                        'Имя': [new_name],
                        'Дата рождения': [new_dob],
                        'Остаток занятий': [new_classes]
                    })
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {new_name} успешно добавлен!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, введите ФИО ученика.")
                    
    with col2:
        st.subheader("Продлить абонемент (Добавить занятия)")
        if not df.empty:
            with st.form("renew_form"):
                student_to_renew = st.selectbox("Выберите ученика", df['Имя'])
                add_classes = st.number_input("Добавить занятий", min_value=1, value=12)
                
                if st.form_submit_button("Продлить абонемент"):
                    # Находим ученика и прибавляем ему занятия
                    idx = df.index[df['Имя'] == student_to_renew].tolist()[0]
                    df.at[idx, 'Остаток занятий'] += add_classes
                    save_data(df)
                    st.success(f"Абонемент ученика '{student_to_renew}' пополнен на {add_classes} занятий!")
                    st.rerun()
        else:
            st.info("Сначала добавьте учеников.")

# --- ВКЛАДКА 3: БАЗА ДАННЫХ ---
with tab3:
    st.header("Текущая база данных")
    if df.empty:
        st.info("База пуста.")
    else:
        # Функция для выделения красным тех, у кого 0 или меньше занятий
        def highlight_zero(val):
            color = '#ff9999' if isinstance(val, (int, float)) and val <= 0 else ''
            return f'background-color: {color}'
        
        # Отображаем таблицу с подсветкой
        st.dataframe(df.style.map(highlight_zero, subset=['Остаток занятий']), use_container_width=True)
        
        # Кнопка для скачивания резервной копии базы данных
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Скачать базу (Резервная копия)",
            data=csv_data,
            file_name=f'students_backup_{date.today()}.csv',
            mime='text/csv',
        )
