import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Имя файла для хранения базы данных
DB_FILE = 'students.csv'

# Функция для вычисления последнего дня текущего месяца
def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

# Функция для загрузки данных
def load_data():
    if not os.path.exists(DB_FILE):
        # Создаем новую структуру с учетом родителей и помесячной оплаты
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
    # Заполняем пустые ячейки посещений пустыми строками, чтобы не было ошибок
    df['Посещения'] = df['Посещения'].fillna('') 
    return df

# Функция для сохранения данных
def save_data(df):
    df.to_csv(DB_FILE, index=False)

# Настройка страницы
st.set_page_config(page_title="Трекер тренера", page_icon="🥋", layout="wide")
st.title("🥋 Журнал тренера: Посещаемость и Оплата (Месяц)")

# Загружаем базу
df = load_data()

# Вкладки
tab1, tab2, tab3 = st.tabs(["📋 Отметка посещаемости", "➕ Ученики и Оплата", "📊 База данных"])

# --- ВКЛАДКА 1: ПОСЕЩАЕМОСТЬ ---
with tab1:
    st.header("Отметка посещаемости")
    today = st.date_input("Дата тренировки", date.today())

    if df.empty:
        st.warning("База учеников пуста. Добавьте учеников во вкладке 'Ученики и Оплата'.")
    else:
        st.write("Отметьте тех, кто присутствует сегодня:")
        
        with st.form("attendance_form"):
            present_students = []
            for index, row in df.iterrows():
                # Проверяем, оплачен ли абонемент
                paid_until = pd.to_datetime(row['Оплачено до']).date()
                if today > paid_until:
                    warning = " 🔴 (ДОЛГ: Месяц не оплачен!)"
                else:
                    warning = f" 🟢 (Оплачено до {paid_until.strftime('%d.%m.%Y')})"
                    
                is_present = st.checkbox(f"{row['Имя ученика']}{warning}", key=f"check_{index}")
                if is_present:
                    present_students.append(index)
            
            submitted = st.form_submit_button("Сохранить посещаемость")
            
            if submitted:
                if not present_students:
                    st.info("Никто не отмечен.")
                else:
                    # Записываем дату тренировки в карточку ученика
                    date_str = today.strftime('%d.%m')
                    for idx in present_students:
                        current_visits = str(df.at[idx, 'Посещения'])
                        if date_str not in current_visits: # Чтобы не записать дважды за один день
                            if current_visits == '':
                                df.at[idx, 'Посещения'] = date_str
                            else:
                                df.at[idx, 'Посещения'] = current_visits + f", {date_str}"
                                
                    save_data(df)
                    st.success(f"Посещаемость за {today.strftime('%d.%m.%Y')} сохранена!")
                    st.rerun()

# --- ВКЛАДКА 2: УПРАВЛЕНИЕ УЧЕНИКАМИ ---
with tab2:
    st.header("Управление учениками и абонементами")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Добавить нового ученика")
        with st.form("add_student_form"):
            new_name = st.text_input("ФИО ученика*")
            new_dob = st.date_input("Дата рождения", min_value=date(2000, 1, 1), max_value=date.today(), value=date(2015, 1, 1))
            new_parent = st.text_input("ФИО родителя")
            new_phone = st.text_input("Телефон родителя (например: +7 999 123 45 67)")
            
            # По умолчанию ставим оплату до конца текущего месяца
            default_paid_until = get_end_of_month(date.today())
            new_paid_until = st.date_input("Оплачено до (включительно)", value=default_paid_until)
            
            if st.form_submit_button("Добавить ученика"):
                if new_name:
                    new_student = pd.DataFrame({
                        'Имя ученика': [new_name],
                        'Дата рождения': [new_dob],
                        'ФИО родителя': [new_parent],
                        'Телефон': [new_phone],
                        'Оплачено до': [new_paid_until],
                        'Посещения': ['']
                    })
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {new_name} успешно добавлен!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, введите ФИО ученика (это обязательное поле).")
                    
    with col2:
        st.subheader("Продлить абонемент (Отметить оплату)")
        if not df.empty:
            with st.form("renew_form"):
                student_to_renew = st.selectbox("Выберите ученика", df['Имя ученика'])
                # Предлагаем дату: конец следующего месяца
                next_month_date = date.today().replace(day=28) + pd.Timedelta(days=4) # Перескакиваем в следующий месяц
                suggested_date = get_end_of_month(next_month_date)
                
                renew_date = st.date_input("Новая дата 'Оплачено до'", value=suggested_date)
                
                # Кнопка для очистки истории посещений (удобно в начале нового месяца)
                clear_visits = st.checkbox("Очистить историю посещений (начался новый месяц)")
                
                if st.form_submit_button("Сохранить оплату"):
                    idx = df.index[df['Имя ученика'] == student_to_renew].tolist()[0]
                    df.at[idx, 'Оплачено до'] = renew_date
                    if clear_visits:
                        df.at[idx, 'Посещения'] = ''
                    save_data(df)
                    st.success(f"Оплата для '{student_to_renew}' зафиксирована до {renew_date.strftime('%d.%m.%Y')}!")
                    st.rerun()
        else:
            st.info("Сначала добавьте учеников в базу.")

# --- ВКЛАДКА 3: БАЗА ДАННЫХ ---
with tab3:
    st.header("Текущая база данных")
    if df.empty:
        st.info("База пуста.")
    else:
        # Подсвечиваем красным тех, кто просрочил оплату
        def highlight_unpaid(row):
            paid_date = pd.to_datetime(row['Оплачено до']).date()
            color = '#ff9999' if date.today() > paid_date else ''
            return [f'background-color: {color}'] * len(row)
        
        st.dataframe(df.style.apply(highlight_unpaid, axis=1), use_container_width=True)
        
        # Кнопка скачивания
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Скачать базу (Резервная копия Excel)",
            data=csv_data,
            file_name=f'students_backup_{date.today()}.csv',
            mime='text/csv',
        )
