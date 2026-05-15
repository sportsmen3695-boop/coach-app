import streamlit as st
import pandas as pd
from datetime import date
import calendar
import os

# --- НАСТРОЙКИ ---
DB_FILE = 'students_db.csv'
DEFAULT_PRICE_MONTH = 2500
PRICE_PER_SESSION = 250
PERCENT_DIR = 0.40

BASE_COLUMNS = ['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до', 'Сумма']
FULL_COLUMNS = ['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Тип оплаты', 'Оплачено до', 'Баланс занятий', 'Сумма', 'Посещения']


def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)


def upgrade_dataframe(df):
    if 'Тип оплаты' not in df.columns:
        df['Тип оплаты'] = 'Абонемент'
    if 'Баланс занятий' not in df.columns:
        df['Баланс занятий'] = 0
    if 'Посещения' not in df.columns:
        df['Посещения'] = ''

    df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    # ИСПРАВЛЕНИЕ: используем pd.to_numeric с fillna перед astype чтобы избежать ошибок на NaN
    df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(DEFAULT_PRICE_MONTH).astype(int)
    df['Баланс занятий'] = pd.to_numeric(df['Баланс занятий'], errors='coerce').fillna(0).astype(int)
    df['Посещения'] = df['Посещения'].fillna('').astype(str).replace('nan', '')

    return df[FULL_COLUMNS]


def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=FULL_COLUMNS)
        df.to_csv(DB_FILE, index=False)
        return df

    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df = upgrade_dataframe(df)
    return df


def save_data(df):
    df.to_csv(DB_FILE, index=False)


def check_debt(row, today_dt):
    """ИСПРАВЛЕНИЕ: единообразное сравнение дат через pd.Timestamp."""
    if row['Тип оплаты'] == 'Абонемент':
        val = row['Оплачено до']
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return True
        paid_ts = pd.to_datetime(val, errors='coerce')
        return pd.isna(paid_ts) or paid_ts < today_dt
    else:
        return row['Баланс занятий'] <= 0


# ИСПРАВЛЕНИЕ: функции больше не зависят от колонки 'Должник' в row —
# вычисляют статус напрямую, чтобы работать независимо от порядка apply()
def calc_active_value(row, today_dt):
    is_debt = check_debt(row, today_dt)
    if row['Тип оплаты'] == 'Абонемент':
        return row['Сумма'] if not is_debt else 0
    else:
        return row['Баланс занятий'] * PRICE_PER_SESSION if row['Баланс занятий'] > 0 else 0


def calc_debt_value(row, today_dt):
    is_debt = check_debt(row, today_dt)
    if row['Тип оплаты'] == 'Абонемент':
        return row['Сумма'] if is_debt else 0
    else:
        return abs(row['Баланс занятий']) * PRICE_PER_SESSION if row['Баланс занятий'] < 0 else 0


st.set_page_config(page_title="Coach Finance Pro", page_icon="🥋", layout="wide")

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
today_dt = pd.to_datetime(today)

if not df.empty:
    df['Должник'] = df.apply(lambda row: check_debt(row, today_dt), axis=1)

# --- ПАНЕЛЬ ЗАДАЧ ---
with st.sidebar:
    st.title("🥋 МЕНЮ")
    page = st.radio("Перейти:", ["📊 Дашборд", "📅 Посещаемость", "➕ Регистрация", "⚙️ Оплата"])
    st.divider()

    st.subheader("💾 РЕЗЕРВНАЯ КОПИЯ")

    if not df.empty:
        export_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Скачать базу",
            data=csv,
            file_name=f"students_backup_{today}.csv",
            mime="text/csv",
        )

    uploaded_file = st.file_uploader("📤 Восстановить", type=None)
    if uploaded_file is not None:
        try:
            new_df = pd.read_csv(uploaded_file)
            if all(col in new_df.columns for col in BASE_COLUMNS):
                new_df = upgrade_dataframe(new_df)
                save_data(new_df)
                st.success("Успех! База обновлена.")
                st.rerun()
            else:
                st.error("❌ Неверный формат файла.")
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")

    st.divider()

    if not df.empty:
        debtors_count = df['Должник'].sum()
        if debtors_count > 0:
            st.error(f"🔴 Должников: {debtors_count}")
        else:
            st.success("🟢 Все оплачено")

# --- ЛОГИКА СТРАНИЦ ---

if page == "📊 Дашборд":
    st.title("Финансовый отчет")
    if not df.empty:
        # ИСПРАВЛЕНИЕ: передаём today_dt явно в лямбду
        df['Активная ценность'] = df.apply(lambda row: calc_active_value(row, today_dt), axis=1)
        df['Сумма долга'] = df.apply(lambda row: calc_debt_value(row, today_dt), axis=1)

        active_subscriptions_value = df['Активная ценность'].sum()
        debt_value = df['Сумма долга'].sum()

        director_share = active_subscriptions_value * PERCENT_DIR
        coach_income = active_subscriptions_value - director_share

        c1, c2, c3 = st.columns(3)
        with c1:
            delta_val = f"-{int(debt_value)} ₽ (долг)" if debt_value > 0 else "Долгов нет"
            st.metric("Ценность активной базы", f"{int(active_subscriptions_value)} ₽",
                      delta=delta_val, delta_color="normal",
                      help="Сумма всех оплаченных абонементов и остатка купленных разовых тренировок.")
        with c2:
            st.metric("Доля клуба (40%)", f"{int(director_share)} ₽")
        with c3:
            st.metric("Ваша чистая ЗП", f"{int(coach_income)} ₽")

        st.divider()
        search = st.text_input("🔍 Поиск по имени", placeholder="Введите имя...")

        view_df = df.drop(columns=['Должник', 'Активная ценность', 'Сумма долга']).copy()
        view_df['Сортировка'] = view_df.apply(lambda r: 0 if check_debt(r, today_dt) else 1, axis=1)
        view_df = view_df.sort_values(by=['Сортировка', 'Имя ученика']).drop(columns=['Сортировка'])

        # ИСПРАВЛЕНИЕ: заменяем NaT/None на строку после сортировки
        view_df['Оплачено до'] = view_df['Оплачено до'].apply(
            lambda v: 'Нет' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        )

        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search, case=False, na=False)]

        view_df.index = range(1, len(view_df) + 1)

        def style_rows(row):
            """ИСПРАВЛЕНИЕ: корректная проверка долга для строк с 'Оплачено до' == 'Нет'."""
            is_debt = False
            if row['Тип оплаты'] == 'Абонемент':
                val = row['Оплачено до']
                if val == 'Нет':
                    is_debt = True
                else:
                    paid_ts = pd.to_datetime(val, errors='coerce')
                    is_debt = pd.isna(paid_ts) or paid_ts < today_dt
            else:
                is_debt = row['Баланс занятий'] <= 0

            style = 'background-color: rgba(248, 113, 113, 0.15); color: #fca5a5' if is_debt else ''
            return [style for _ in row]

        st.dataframe(view_df.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("ℹ️ База пуста.")

elif page == "📅 Посещаемость":
    st.title("Журнал тренировок")
    if not df.empty:
        target_date = st.date_input("Выберите дату", value=today)
        target_date_str = target_date.strftime("%Y-%m-%d")

        already_present = []
        for idx, row in df.iterrows():
            # ИСПРАВЛЕНИЕ: безопасный split с проверкой на пустую строку
            raw = str(row['Посещения']).strip()
            visits = [v.strip() for v in raw.split(',') if v.strip()]
            if target_date_str in visits:
                already_present.append(row['Имя ученика'])

        st.write("Отметьте присутствующих:")
        student_list = sorted(df['Имя ученика'].dropna().unique())
        selected_students = st.multiselect("Список группы:", student_list, default=already_present)

        if st.button("💾 Сохранить посещаемость"):
            for idx in df.index:
                student_name = df.at[idx, 'Имя ученика']
                pay_type = df.at[idx, 'Тип оплаты']

                raw_visits = str(df.at[idx, 'Посещения']).strip()
                visits = [v.strip() for v in raw_visits.split(',') if v.strip()]

                is_selected = student_name in selected_students
                was_present_before = target_date_str in visits

                if is_selected and not was_present_before:
                    visits.append(target_date_str)
                    if pay_type == 'Разовая':
                        df.at[idx, 'Баланс занятий'] -= 1

                elif not is_selected and was_present_before:
                    visits.remove(target_date_str)
                    if pay_type == 'Разовая':
                        df.at[idx, 'Баланс занятий'] += 1

                df.at[idx, 'Посещения'] = ','.join(visits)

            save_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
            save_data(save_df)
            st.success("✅ Журнал сохранен! Балансы обновлены.")
            st.rerun()
    else:
        st.info("ℹ️ База пуста.")

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
            pay_type = st.radio("Тип оплаты", ["Абонемент", "Разовая"])

            if pay_type == "Абонемент":
                paid = st.date_input("Оплачено до", value=get_end_of_month(today))
                price = st.number_input("Стоимость (₽)", min_value=0, value=DEFAULT_PRICE_MONTH, step=100)
                balance = 0
            else:
                paid = None  # ИСПРАВЛЕНИЕ: None вместо pd.NaT для CSV-совместимости
                balance = st.number_input("Покупает тренировок (шт)", min_value=1, value=1, step=1)
                st.info(f"К оплате: {balance * PRICE_PER_SESSION} ₽")
                price = balance * PRICE_PER_SESSION

        if st.form_submit_button("СОХРАНИТЬ"):
            if not name:
                st.error("Введите имя!")
            elif not df.empty and name.lower() in df['Имя ученика'].astype(str).str.lower().values:
                st.warning("Ученик уже есть в базе!")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': name, 'Дата рождения': dob, 'ФИО родителя': parent,
                    'Телефон': phone, 'Тип оплаты': pay_type, 'Оплачено до': paid,
                    'Баланс занятий': int(balance), 'Сумма': int(price), 'Посещения': ''
                }])

                save_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
                save_df = pd.concat([save_df, new_row], ignore_index=True)
                save_data(save_df)
                st.success("Сохранено! Не забудь скачать бэкап.")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление и Оплата")
    if not df.empty:
        student_list = sorted(df['Имя ученика'].dropna().unique())
        student = st.selectbox("Выберите ученика", student_list)

        if student:
            row = df[df['Имя ученика'] == student].iloc[0]
            current_type = row['Тип оплаты']

            st.write(f"Текущий режим: **{current_type}**")

            col1, col2 = st.columns(2)

            if current_type == "Абонемент":
                with col1:
                    new_paid = st.date_input("Продлить абонемент до", value=get_end_of_month(today))
                with col2:
                    new_price = st.number_input("Сумма оплаты", min_value=0, value=int(row['Сумма']))
            else:
                with col1:
                    st.metric("Остаток занятий", int(row['Баланс занятий']))
                    add_sessions = st.number_input("Добавить тренировок", min_value=1, value=4, step=1)
                with col2:
                    new_price = add_sessions * PRICE_PER_SESSION
                    st.metric("К оплате", f"{new_price} ₽")

            if st.button("✅ Подтвердить оплату"):
                idx = df[df['Имя ученика'] == student].index[0]

                if current_type == "Абонемент":
                    df.at[idx, 'Оплачено до'] = new_paid
                    df.at[idx, 'Сумма'] = int(new_price)
                else:
                    df.at[idx, 'Баланс занятий'] = int(row['Баланс занятий']) + int(add_sessions)
                    df.at[idx, 'Сумма'] = int(new_price)

                save_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
                save_data(save_df)
                st.success("Оплата сохранена!")
                st.rerun()

            st.divider()

            st.write("🛠 Смена типа оплаты")
            # ИСПРАВЛЕНИЕ: список всегда содержит только противоположный тип
            opposite_type = "Разовая" if current_type == "Абонемент" else "Абонемент"
            st.info(f"Текущий тип: **{current_type}**. Будет изменён на: **{opposite_type}**")

            if st.button("🔄 Изменить режим"):
                idx = df[df['Имя ученика'] == student].index[0]
                df.at[idx, 'Тип оплаты'] = opposite_type
                if opposite_type == "Разовая":
                    df.at[idx, 'Баланс занятий'] = 0
                    df.at[idx, 'Оплачено до'] = None  # ИСПРАВЛЕНИЕ: None вместо pd.NaT
                    df.at[idx, 'Сумма'] = 0
                else:
                    df.at[idx, 'Оплачено до'] = get_end_of_month(today)
                    df.at[idx, 'Баланс занятий'] = 0
                    df.at[idx, 'Сумма'] = DEFAULT_PRICE_MONTH

                save_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
                save_data(save_df)
                st.rerun()

            st.divider()
            if st.button("🗑 Удалить ученика"):
                save_df = df.drop(columns=['Должник']) if 'Должник' in df.columns else df
                save_df = save_df[save_df['Имя ученика'] != student]
                save_data(save_df)
                st.success("Ученик удален.")
                st.rerun()
    else:
        st.info("ℹ️ База пуста.")
