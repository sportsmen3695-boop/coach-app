import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# --- НАСТРОЙКИ ---
# Убрали жесткую привязку к версии в названии, чтобы не плодить файлы
DB_FILE = 'students_db.csv' 
DEFAULT_PRICE = 2500
PERCENT_DIR = 0.40

# Ожидаемые колонки для проверки при восстановлении базы
EXPECTED_COLUMNS = ['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до', 'Сумма']

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)

def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)
        df.to_csv(DB_FILE, index=False)
        return df
    
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        # Безопасная конвертация дат
        df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
        df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
        
        if 'Сумма' not in df.columns:
            df['Сумма'] = DEFAULT_PRICE
        df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(DEFAULT_PRICE).astype(int)
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

st.set_page_config(page_title="Coach Finance Pro", page_icon="💰", layout="wide")

# Темная тема
st.markdown("""
    <style>
    .stApp { background: #0f172a; color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    .stMetric { background: rgba(30, 41, 59, 0.7); padding: 15px; border-radius: 12px; border: 1px solid #334155; }
    .stButton>button { width: 100%; height: 50px; border-radius: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

df = load_data()
today = date.today()

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()
    
    # --- БЛОК СПАСЕНИЯ ДАННЫХ ---
    st.subheader("💾 РЕЗЕРВНАЯ КОПИЯ")
    
    # 1. Кнопка скачивания
    if not df.empty:
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Скачать базу на телефон",
            data=csv,
            file_name=f"students_backup_{today}.csv",
            mime="text/csv",
        )
    
    # 2. Кнопка загрузки (с проверкой структуры!)
    uploaded_file = st.file_uploader("📤 Восстановить из файла", type=["csv", "txt"])
    if uploaded_file is not None:
        try:
            new_df = pd.read_csv(uploaded_file)
            # Проверка: есть ли нужные колонки в загруженном файле
            if all(col in new_df.columns for col in EXPECTED_COLUMNS):
                save_data(new_df)
                st.success("База успешно восстановлена!")
                st.rerun()
            else:
                st.error("❌ Ошибка: Неверный формат файла. Загрузите правильный бэкап.")
        except Exception as e:
            st.error(f"❌ Ошибка чтения файла: {e}")
    
    st.divider()
    
    # Безопасный подсчет должников (учет пустых дат и просроченных)
    if not df.empty:
        today_dt = pd.to_datetime(today)
        # Считаем тех, у кого дата меньше сегодняшней, плюс тех, у кого даты вообще нет (NaT)
        debtors_count = len(df[pd.to_datetime(df['Оплачено до'], errors='coerce') < today_dt]) + df['Оплачено до'].isna().sum()
        
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---
if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    if not df.empty:
        today_dt = pd.to_datetime(today)
        
        # Безопасная маска для фильтрации дат
        paid_mask = pd.to_datetime(df['Оплачено до'], errors='coerce') >= today_dt
        paid_df = df[paid_mask]
        unpaid_df = df[~paid_mask]
        
        # Метрики переименованы для прозрачности логики
        active_subscriptions_value = paid_df['Сумма'].sum()
        debt_value = unpaid_df['Сумма'].sum()
        
        director_share = active_subscriptions_value * PERCENT_DIR
        coach_income = active_subscriptions_value - director_share

        c1, c2, c3 = st.columns(3)
        with c1:
            delta_val = f"-{int(debt_value)} ₽ (долг)" if debt_value > 0 else "Долгов нет"
            # Название метрики изменено, чтобы не путать с "собранными за месяц деньгами"
            st.metric("Объем активных абонементов", f"{int(active_subscriptions_value)} ₽", delta=delta_val, delta_color="normal")
        with c2:
            st.metric("Доля клуба (40%)", f"{int(director_share)} ₽")
        with c3:
            st.metric("Ваша чистая ЗП", f"{int(coach_income)} ₽")

        st.divider()
        search = st.text_input("🔍 Поиск по имени", placeholder="Введите имя...")
        view_df = df.copy()
        
        # Безопасная сортировка по дате (позволяет избежать ошибок с NaT)
        view_df['Оплачено до (сортировка)'] = pd.to_datetime(view_df['Оплачено до'], errors='coerce')
        view_df = view_df.sort_values(by='Оплачено до (сортировка)', ascending=True).drop(columns=['Оплачено до (сортировка)'])
        
        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search, case=False, na=False)]
        
        view_df.index = range(1, len(view_df) + 1)
        
        # Безопасная функция подсветки строк (проверка на пустые значения)
        def style_rows(row):
            val = row['Оплачено до']
            is_debt = pd.isna(val) or (isinstance(val, date) and val < today)
            return ['background-color: rgba(248, 113, 113, 0.15); color: #fca5a5' if is_debt else '' for _ in row]

        st.dataframe(view_df.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        # Заглушка, если база пустая
        st.info("ℹ️ База пуста. Добавьте учеников во вкладке 'Регистрация' или восстановите из файла в меню слева.")

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
            paid = st.date_input("Оплачено до", value=get_end_of_month(today))
            price = st.number_input("Стоимость абонемента (₽)", min_value=0, value=DEFAULT_PRICE, step=100)
        
        if st.form_submit_button("СОХРАНИТЬ"):
            if not name:
                st.error("Введите имя!")
            elif not df.empty and name.lower() in df['Имя ученика'].astype(str).str.lower().values:
                st.warning(f"Ученик '{name}' уже есть в базе!")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': name, 'Дата рождения': dob, 'ФИО родителя': parent,
                    'Телефон': phone, 'Оплачено до': paid, 'Сумма': int(price)
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_data(df)
                st.success(f"Добавлен: {name}. Не забудь скачать базу в конце работы!")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление")
    if not df.empty:
        # Безопасная загрузка списка учеников (исключаем пустые имена)
        student_list = sorted(df['Имя ученика'].dropna().unique())
        student = st.selectbox("Выберите ученика", student_list)
        
        if student:
            row = df[df['Имя ученика'] == student].iloc[0]
            col1, col2 = st.columns(2)
            
            with col1:
                new_paid = st.date_input("Продлить оплату до", value=get_end_of_month(today))
            with col2:
                new_price = st.number_input("Стоимость", min_value=0, value=int(row['Сумма']))
            
            if st.button("✅ Подтвердить оплату"):
                idx = df[df['Имя ученика'] == student].index[0]
                df.at[idx, 'Оплачено до'] = new_paid
                df.at[idx, 'Сумма'] = int(new_price)
                save_data(df)
                st.success(f"Обновлено! Скачай базу для сохранения.")
                st.rerun()
            
            st.divider()
            if st.button("🗑 Удалить ученика"):
                df = df[df['Имя ученика'] != student]
                save_data(df)
                st.success(f"Ученик удален.")
                st.rerun()
    else:
        # Заглушка, если база пустая
        st.info("ℹ️ База пуста. Добавьте учеников во вкладке 'Регистрация'.")
