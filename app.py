import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# Версия v13 - добавлена индивидуальная сумма оплаты
DB_FILE = 'students_v13.csv'
DEFAULT_PRICE = 2500  # Цена по умолчанию
PERCENT_DIR = 0.40    # Доля директора (40%)

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        # Добавлена колонка 'Сумма'
        df = pd.DataFrame(columns=['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до', 'Сумма'])
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
        # Заполняем пустые суммы дефолтным значением, если они есть
        if 'Сумма' not in df.columns:
            df['Сумма'] = DEFAULT_PRICE
        df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(DEFAULT_PRICE)
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- ДИЗАЙН ---
st.set_page_config(page_title="Coach Finance Pro", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #0f172a; color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    .stMetric { background: rgba(30, 41, 59, 0.7); padding: 15px; border-radius: 12px; border: 1px solid #334155; }
    .stButton>button { width: 100%; height: 50px; border-radius: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

df = load_data()

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    if not df.empty:
        total_count = len(df)
        valid_dates = df.dropna(subset=['Оплачено до'])
        paid_count = len(valid_dates[valid_dates['Оплачено до'] >= date.today()])
        debtors_count = total_count - paid_count
        
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    
    if not df.empty:
        # --- ФИНАНСОВЫЕ РАСЧЕТЫ ---
        today = date.today()
        
        # Оплатившие: те, у кого дата оплаты сегодня или в будущем
        paid_df = df[df['Оплачено до'] >= today]
        # Должники: все остальные
        unpaid_df = df[df['Оплачено до'] < today]
        
        collected_money = paid_df['Сумма'].sum()
        remaining_money = unpaid_df['Сумма'].sum()
        
        director_share = collected_money * PERCENT_DIR
        coach_income = collected_money - director_share

        # Вывод карточек
        c1, c2, c3 = st.columns(3)
        with c1:
            delta_val = f"-{int(remaining_money)} ₽ (долг)" if remaining_money > 0 else "Долгов нет"
            st.metric("Собрано (всего)", f"{int(collected_money)} ₽", delta=delta_val, delta_color="normal")
        with c2:
            st.metric("Доля директора (40%)", f"{int(director_share)} ₽")
        with c3:
            st.metric("Ваша чистая ЗП", f"{int(coach_income)} ₽")

        st.divider()
        
        # --- ТАБЛИЦА ---
        search = st.text_input("🔍 Быстрый поиск", placeholder="Имя ученика...")
        view_df = df.copy()
        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search, case=False, na=False)]
        
        view_df.index = range(1, len(view_df) + 1)
        
        def style_rows(row):
            is_debt = pd.isna(row['Оплачено до']) or row['Оплачено до'] < date.today()
            return ['background-color: rgba(248, 113, 113, 0.15); color: #fca5a5' if is_debt else '' for _ in row]

        st.dataframe(view_df.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("Добавьте учеников для расчета статистики.")

elif page == "➕ Регистрация":
    st.title("Новый ученик")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("ФИО ученика*").strip()
            dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            parent = st.text_input("Родитель")
        with col2:
            phone = st.text_input("Телефон")
            paid = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            # НОВОЕ ПОЛЕ: Сумма абонемента
            price = st.number_input("Стоимость абонемента (₽)", min_value=0, value=DEFAULT_PRICE, step=100)
        
        if st.form_submit_button("СОХРАНИТЬ"):
            if not name:
                st.error("Введите имя!")
            elif not df.empty and name.lower() in df['Имя ученика'].astype(str).str.lower().values:
                st.warning(f"Ученик '{name}' уже есть в базе!")
            else:
                new_data = pd.DataFrame([{
                    'Имя ученика': name, 
                    'Дата рождения': dob, 
                    'ФИО родителя': parent, 
                    'Телефон': phone, 
                    'Оплачено до': paid,
                    'Сумма': price
                }])
                df = pd.concat([df, new_data], ignore_index=True)
                save_data(df)
                st.success(f"Ученик {name} добавлен с оплатой {price} ₽")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление")
    if not df.empty:
        student = st.selectbox("Выбор ученика", sorted(df['Имя ученика'].astype(str).unique()))
        
        # Получаем текущую сумму ученика, чтобы её можно было изменить при оплате
        current_price = df[df['Имя ученика'] == student]['Сумма'].values[0]
        
        new_paid = st.date_input("Продлить до", value=get_end_of_month(date.today()))
        new_price = st.number_input("Изменить стоимость (если нужно)", min_value=0, value=int(current_price))
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Подтвердить оплату"):
            idx = df[df['Имя ученика'] == student].index[0]
            df.at[idx, 'Оплачено до'] = new_paid
            df.at[idx, 'Сумма'] = new_price
            save_data(df)
            st.success("Оплата и сумма обновлены")
            st.rerun()
        
        if c2.button("🗑 Удалить ученика"):
            df = df[df['Имя ученика'] != student]
            save_data(df)
            st.rerun()
