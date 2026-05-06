import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os
import uuid

# Версия v13.1 - исправлены синтаксические ошибки и переносы строк
DB_FILE = 'students_v13.csv'
PAYMENTS_FILE = 'payments_v13.csv'
PRICE = 2500  # Стоимость абонемента
PERCENT_DIR = 0.40  # Доля директора (40%)

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_students():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=['ID', 'Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до'])
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE, dtype={'ID': str, 'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    return df

def load_payments():
    if not os.path.exists(PAYMENTS_FILE):
        df = pd.DataFrame(columns=['Дата платежа', 'ID', 'Сумма'])
        df.to_csv(PAYMENTS_FILE, index=False)
        return df
    df = pd.read_csv(PAYMENTS_FILE, dtype={'ID': str})
    if not df.empty:
        df['Дата платежа'] = pd.to_datetime(df['Дата платежа'], errors='coerce').dt.date
        df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(0)
    return df

def save_data(df, file_name):
    df.to_csv(file_name, index=False)

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

df_students = load_students()
df_payments = load_payments()

# Единая логика определения должников
debtors_mask = pd.Series(False, index=df_students.index)
if not df_students.empty:
    valid_dates = pd.notna(df_students['Оплачено до'])
    debtors_mask = valid_dates & (df_students['Оплачено до'] < date.today())
debtors_count = debtors_mask.sum()

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    if not df_students.empty:
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    
    if not df_students.empty:
        today = date.today()
        
        # Считаем кассу только за ТЕКУЩИЙ месяц
        collected_money = 0
        if not df_payments.empty:
            current_month_payments = df_payments[
                (pd.to_datetime(df_payments['Дата платежа']).dt.month == today.month) &
                (pd.to_datetime(df_payments['Дата платежа']).dt.year == today.year)
            ]
            collected_money = current_month_payments['Сумма'].sum()
        
        # Потенциальный долг (сколько еще должны донести)
        remaining_money = debtors_count * PRICE
        
        director_share = collected_money * PERCENT_DIR
        coach_income = collected_money - director_share

        st.caption(f"Статистика за {today.strftime('%m.%Y')}")
        c1, c2, c3 = st.columns(3)
        with c1:
            # ИСПРАВЛЕНО: синтаксис собран в одну безопасную строку без разрывов скобок
            st.metric(
                label="Собрано в этом месяце", 
                value=f"{int(collected_money)} ₽", 
                delta=f"Ожидаем долг: {int(remaining_money)} ₽", 
                delta_color="inverse"
            )
        with c2:
            st.metric("Доля директора (40%)", f"{int(director_share)} ₽")
        with c3:
            st.metric("Ваша чистая ЗП", f"{int(coach_income)} ₽")

        st.divider()
        
        # --- ТАБЛИЦА УЧЕНИКОВ ---
        search = st.text_input("🔍 Быстрый поиск", placeholder="Имя ученика...")
        view_df = df_students.copy()
        
        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search.strip(), case=False, na=False)]
        
        # Визуальное оформление должников
        def style_rows(row):
            is_debt = pd.notna(row['Оплачено до']) and row['Оплачено до'] < date.today()
            return ['background-color: rgba(248, 113, 113, 0.15); color: #fca5a5' if is_debt else '' for _ in row]

        display_cols = ['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до']
        st.dataframe(view_df[display_cols].style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("Добавьте учеников для расчета статистики.")

elif page == "➕ Регистрация":
    st.title("Новый ученик")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("ФИО ученика*").strip()
        dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
        parent = st.text_input("Родитель").strip()
        phone = st.text_input("Телефон").strip()
        paid = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
        
        is_paid_now = st.checkbox("Оплатил абонемент сейчас", value=True)
        
        if st.form_submit_button("СОХРАНИТЬ"):
            if not name:
                st.error("Введите имя!")
            else:
                student_id = uuid.uuid4().hex[:6].upper()
                
                # 1. Сохраняем анкету
                new_student = pd.DataFrame([{
                    'ID': student_id,
                    'Имя ученика': name, 
                    'Дата рождения': dob, 
                    'ФИО родителя': parent, 
                    'Телефон': phone, 
                    'Оплачено до': paid
                }])
                df_students = pd.concat([df_students, new_student], ignore_index=True)
                save_data(df_students, DB_FILE)
                
                # 2. Если оплатил, заносим в кассу (payments)
                if is_paid_now:
                    new_payment = pd.DataFrame([{
                        'Дата платежа': date.today(),
                        'ID': student_id,
                        'Сумма': PRICE
                    }])
                    df_payments = pd.concat([df_payments, new_payment], ignore_index=True)
                    save_data(df_payments, PAYMENTS_FILE)
                
                st.success(f"Ученик {name} добавлен!")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление")
    if not df_students.empty:
        student_options = [f"{row['Имя ученика']} | ID: {row['ID']}" for _, row in df_students.iterrows()]
        selected = st.selectbox("Выбор ученика", sorted(student_options))
        
        selected_id = selected.split(" | ID: ")[1]
        student_idx = df_students[df_students['ID'] == selected_id].index[0]
        
        st.divider()
        st.subheader("Продление абонемента")
        
        payment_amount = st.number_input("Сумма оплаты (₽)", value=PRICE, step=500)
        new_paid = st.date_input("Продлить до", value=get_end_of_month(date.today()))
        
        if st.button("✅ Подтвердить оплату", type="primary"):
            # 1. Обновляем дату ученику
            df_students.at[student_idx, 'Оплачено до'] = new_paid
            save_data(df_students, DB_FILE)
            
            # 2. Записываем транзакцию
            new_payment = pd.DataFrame([{
                'Дата платежа': date.today(),
                'ID': selected_id,
                'Сумма': payment_amount
            }])
            df_payments = pd.concat([df_payments, new_payment], ignore_index=True)
            save_data(df_payments, PAYMENTS_FILE)
            
            st.success("Оплата успешно зачислена!")
            st.rerun()
        
        st.divider()
        st.subheader("Опасная зона")
        confirm_delete = st.checkbox("Подтверждаю удаление ученика")
        if st.button("🗑 Удалить карточку", disabled=not confirm_delete):
            df_students = df_students.drop(student_idx)
            save_data(df_students, DB_FILE)
            st.success("Ученик удален из базы")
            st.rerun()
