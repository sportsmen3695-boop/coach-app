import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import os
import json

# --- НАСТРОЙКИ ---
DB_FILE = 'students_db.csv'
PAYMENTS_FILE = 'payments_log.csv'
DEFAULT_PRICE_MONTH = 2500
PRICE_PER_SESSION = 250
PERCENT_DIR = 0.40

BASE_COLUMNS = ['Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон', 'Оплачено до', 'Сумма']
FULL_COLUMNS = [
    'Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон',
    'Тип оплаты', 'Оплачено до', 'Баланс занятий', 'Сумма', 'Посещения'
]
PAYMENT_COLUMNS = ['Дата', 'Имя ученика', 'Тип', 'Описание', 'Сумма']


# ─────────────────────────────────────────────
# УТИЛИТЫ
# ─────────────────────────────────────────────

def get_end_of_month(current_date):
    _, last_day = calendar.monthrange(current_date.year, current_date.month)
    return date(current_date.year, current_date.month, last_day)


def parse_visits(raw) -> list:
    """Безопасный парсинг поля Посещения → список строк дат."""
    raw = str(raw).strip()
    if not raw or raw.lower() in ('nan', 'none', ''):
        return []
    return [v.strip() for v in raw.split(',') if v.strip()]


def visits_to_str(visits: list) -> str:
    return ','.join(sorted(set(visits)))


def is_debt(row, today_dt) -> bool:
    """Проверка наличия долга. Возвращает True, если ученик должен."""
    if row['Тип оплаты'] == 'Абонемент':
        val = row['Оплачено до']
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return True
        paid_ts = pd.to_datetime(val, errors='coerce')
        return pd.isna(paid_ts) or paid_ts < today_dt
    else:
        # Для разовых — долг если баланс отрицательный (не нулевой!)
        return row['Баланс занятий'] < 0


def active_value(row, today_dt) -> int:
    """Сумма, которую ученик уже оплатил и которая ещё «активна»."""
    if is_debt(row, today_dt):
        return 0
    if row['Тип оплаты'] == 'Абонемент':
        return int(row['Сумма'])
    else:
        return max(0, int(row['Баланс занятий'])) * PRICE_PER_SESSION


def debt_value(row, today_dt) -> int:
    """Сумма задолженности."""
    if not is_debt(row, today_dt):
        return 0
    if row['Тип оплаты'] == 'Абонемент':
        return int(row['Сумма']) if int(row['Сумма']) > 0 else DEFAULT_PRICE_MONTH
    else:
        return max(0, -int(row['Баланс занятий'])) * PRICE_PER_SESSION


# ─────────────────────────────────────────────
# БАЗА ДАННЫХ
# ─────────────────────────────────────────────

def upgrade_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if 'Тип оплаты' not in df.columns:
        df['Тип оплаты'] = 'Абонемент'
    if 'Баланс занятий' not in df.columns:
        df['Баланс занятий'] = 0
    if 'Посещения' not in df.columns:
        df['Посещения'] = ''

    df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(DEFAULT_PRICE_MONTH).astype(int)
    df['Баланс занятий'] = pd.to_numeric(df['Баланс занятий'], errors='coerce').fillna(0).astype(int)
    df['Посещения'] = df['Посещения'].fillna('').astype(str).replace('nan', '')
    return df[FULL_COLUMNS]


def load_data() -> pd.DataFrame:
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=FULL_COLUMNS)
        df.to_csv(DB_FILE, index=False)
        return df
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    if not df.empty:
        df = upgrade_dataframe(df)
    return df


def save_data(df: pd.DataFrame):
    save_df = df.drop(columns=['Должник'], errors='ignore')
    save_df.to_csv(DB_FILE, index=False)


def load_payments() -> pd.DataFrame:
    if not os.path.exists(PAYMENTS_FILE):
        df = pd.DataFrame(columns=PAYMENT_COLUMNS)
        df.to_csv(PAYMENTS_FILE, index=False)
        return df
    return pd.read_csv(PAYMENTS_FILE)


def save_payments(df: pd.DataFrame):
    df.to_csv(PAYMENTS_FILE, index=False)


def log_payment(student: str, pay_type: str, description: str, amount: int):
    payments = load_payments()
    new_row = pd.DataFrame([{
        'Дата': date.today().isoformat(),
        'Имя ученика': student,
        'Тип': pay_type,
        'Описание': description,
        'Сумма': amount,
    }])
    payments = pd.concat([payments, new_row], ignore_index=True)
    save_payments(payments)


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.set_page_config(page_title="Coach Finance Pro", page_icon="🥋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Inter:wght@400;500&display=swap');

.stApp { background: #0a0f1e; color: #e2e8f0; font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#111827 0%,#0d1520 100%) !important; border-right: 1px solid #1e3a5f; }

h1, h2, h3 { font-family: 'Rajdhani', sans-serif; letter-spacing: 0.05em; }

.stMetric { background: rgba(14,30,54,0.8); padding: 18px; border-radius: 14px;
    border: 1px solid #1e3a5f; backdrop-filter: blur(6px); }
.stMetric label { color: #64748b !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.1em; }
.stMetric [data-testid="metric-container"] > div:nth-child(2) { font-family: 'Rajdhani', sans-serif; font-size: 2rem !important; }

.stButton>button { width: 100%; border-radius: 10px; font-weight: 600;
    background: linear-gradient(135deg,#1d4ed8,#1e40af); border: none; color: #fff; padding: 0.6rem 1rem; }
.stButton>button:hover { background: linear-gradient(135deg,#2563eb,#1d4ed8); transform: translateY(-1px); box-shadow: 0 4px 15px rgba(37,99,235,0.4); }

div[data-testid="stForm"] { background: rgba(14,30,54,0.5); border-radius: 16px; padding: 20px;
    border: 1px solid #1e3a5f; }

.visit-chip { display:inline-block; background:rgba(16,185,129,0.15); color:#34d399;
    border:1px solid rgba(52,211,153,0.3); border-radius:6px; padding:2px 8px;
    font-size:0.75rem; margin:2px; }

.debt-chip { background:rgba(239,68,68,0.15); color:#f87171; border-color:rgba(248,113,113,0.3); }

.badge-green { background:rgba(16,185,129,0.2); color:#34d399; border-radius:20px;
    padding:3px 10px; font-size:0.75rem; font-weight:600; border:1px solid rgba(52,211,153,0.3); }
.badge-red { background:rgba(239,68,68,0.2); color:#f87171; border-radius:20px;
    padding:3px 10px; font-size:0.75rem; font-weight:600; border:1px solid rgba(248,113,113,0.3); }
.badge-yellow { background:rgba(234,179,8,0.2); color:#fbbf24; border-radius:20px;
    padding:3px 10px; font-size:0.75rem; font-weight:600; border:1px solid rgba(251,191,36,0.3); }

.stat-card { background: rgba(14,30,54,0.7); border-radius:12px; padding:14px 18px;
    border:1px solid #1e3a5f; margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

df = load_data()
today = date.today()
today_dt = pd.to_datetime(today)

if not df.empty:
    df['Должник'] = df.apply(lambda row: is_debt(row, today_dt), axis=1)

# ─── САЙДБАР ───
with st.sidebar:
    st.markdown("## 🥋 ТРЕНЕР PRO")
    page = st.radio("", ["📊 Дашборд", "📅 Посещаемость", "📋 История оплат", "➕ Регистрация", "⚙️ Оплата"], label_visibility="collapsed")
    st.divider()

    st.subheader("💾 РЕЗЕРВНАЯ КОПИЯ")
    if not df.empty:
        export_df = df.drop(columns=['Должник'], errors='ignore')
        csv_bytes = export_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать базу учеников", data=csv_bytes,
                           file_name=f"students_{today}.csv", mime="text/csv")

    payments = load_payments()
    if not payments.empty:
        pay_csv = payments.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать историю оплат", data=pay_csv,
                           file_name=f"payments_{today}.csv", mime="text/csv")

    uploaded_file = st.file_uploader("📤 Восстановить базу", type=None)
    if uploaded_file is not None:
        try:
            new_df = pd.read_csv(uploaded_file)
            if all(col in new_df.columns for col in BASE_COLUMNS):
                new_df = upgrade_dataframe(new_df)
                save_data(new_df)
                st.success("✅ База обновлена!")
                st.rerun()
            else:
                st.error("❌ Неверный формат файла.")
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")

    st.divider()
    if not df.empty:
        debtors = int(df['Должник'].sum())
        total = len(df)
        st.markdown(f"**Учеников:** {total}")
        if debtors > 0:
            st.markdown(f'<span class="badge-red">🔴 Должников: {debtors}</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-green">🟢 Все оплачено</span>', unsafe_allow_html=True)

        # Предупреждение: абонементы истекают в течение 3 дней
        if not df.empty:
            soon = df[
                (df['Тип оплаты'] == 'Абонемент') &
                (df['Должник'] == False) &
                (df['Оплачено до'].apply(
                    lambda v: v is not None and not (isinstance(v, float) and pd.isna(v)) and
                              pd.to_datetime(v, errors='coerce') <= today_dt + pd.Timedelta(days=3)
                ))
            ]
            if not soon.empty:
                st.markdown(f'<span class="badge-yellow">⚠️ Истекает скоро: {len(soon)}</span>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: ДАШБОРД
# ─────────────────────────────────────────────

if page == "📊 Дашборд":
    st.title("Финансовый отчёт")

    if not df.empty:
        df['_active'] = df.apply(lambda r: active_value(r, today_dt), axis=1)
        df['_debt'] = df.apply(lambda r: debt_value(r, today_dt), axis=1)

        total_active = int(df['_active'].sum())
        total_debt = int(df['_debt'].sum())
        director_share = int(total_active * PERCENT_DIR)
        coach_net = total_active - director_share

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("💰 Активная база", f"{total_active:,} ₽",
                      help="Сумма оплаченных абонементов + остаток разовых занятий")
        with c2:
            st.metric("🏢 Доля клуба (40%)", f"{director_share:,} ₽")
        with c3:
            st.metric("👤 Ваша чистая ЗП", f"{coach_net:,} ₽")
        with c4:
            delta = f"⚠️ Долг: {total_debt:,} ₽" if total_debt > 0 else "Долгов нет"
            st.metric("🔴 Задолженность", f"{int(df['Должник'].sum())} чел.", delta=delta,
                      delta_color="inverse" if total_debt > 0 else "normal")

        st.divider()

        # Сводка по типам оплаты
        col_a, col_b = st.columns(2)
        with col_a:
            sub_df = df[df['Тип оплаты'] == 'Абонемент']
            st.markdown(f"""
            <div class="stat-card">
                <b>📋 Абонементы</b><br>
                Всего: {len(sub_df)} | Активных: {int((~sub_df['Должник']).sum())} |
                Должников: {int(sub_df['Должник'].sum())}
            </div>""", unsafe_allow_html=True)
        with col_b:
            sess_df = df[df['Тип оплаты'] == 'Разовая']
            st.markdown(f"""
            <div class="stat-card">
                <b>🎯 Разовые занятия</b><br>
                Всего: {len(sess_df)} | Есть баланс: {int((sess_df['Баланс занятий'] > 0).sum())} |
                Баланс 0: {int((sess_df['Баланс занятий'] == 0).sum())}
            </div>""", unsafe_allow_html=True)

        st.divider()
        search = st.text_input("🔍 Поиск по имени", placeholder="Введите имя...")

        # Подготовка таблицы для отображения
        view_df = df.drop(columns=['Должник', '_active', '_debt'], errors='ignore').copy()

        # Вычисляем ключ сортировки: долгники сверху, потом по алфавиту
        def sort_key(row):
            debt = is_debt(row, today_dt)
            # Для абонементов — сортируем по дате окончания (просроченные — самые ранние)
            if row['Тип оплаты'] == 'Абонемент':
                val = row['Оплачено до']
                dt = pd.to_datetime(val, errors='coerce')
                if pd.isna(dt):
                    return (0, pd.Timestamp.min, row['Имя ученика'])
                return (0 if debt else 1, dt, row['Имя ученика'])
            else:
                return (0 if debt else 1, pd.Timestamp.min, row['Имя ученика'])

        view_df['_sort'] = view_df.apply(sort_key, axis=1)
        view_df = view_df.sort_values(by='_sort').drop(columns=['_sort'])

        # Форматирование
        view_df['Оплачено до'] = view_df['Оплачено до'].apply(
            lambda v: '—' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))

        # Добавляем колонку «Статус»
        def status_label(row):
            if row['Тип оплаты'] == 'Абонемент':
                val = row['Оплачено до']
                if val == '—':
                    return '❌ Не оплачен'
                dt = pd.to_datetime(val, errors='coerce')
                if pd.isna(dt) or dt < today_dt:
                    return f'❌ Просрочен'
                elif dt <= today_dt + pd.Timedelta(days=3):
                    return f'⚠️ Истекает'
                return '✅ Активен'
            else:
                bal = int(row['Баланс занятий'])
                if bal > 0:
                    return f'✅ {bal} занятий'
                elif bal == 0:
                    return '⚠️ Закончились'
                else:
                    return f'❌ Долг {-bal} зан.'

        view_df['Статус'] = view_df.apply(status_label, axis=1)

        # Кол-во посещений всего
        view_df['Всего посещений'] = view_df['Посещения'].apply(lambda v: len(parse_visits(v)))

        # Убираем сырые данные посещений из таблицы
        display_cols = ['Имя ученика', 'Тип оплаты', 'Статус', 'Оплачено до',
                        'Баланс занятий', 'Сумма', 'Всего посещений', 'Телефон', 'ФИО родителя']
        view_df = view_df[display_cols]

        if search:
            view_df = view_df[view_df['Имя ученика'].astype(str).str.contains(search.strip(), case=False, na=False)]

        view_df.index = range(1, len(view_df) + 1)

        def style_rows(row):
            debt_flag = False
            warn_flag = False
            status = row.get('Статус', '')
            if '❌' in str(status):
                debt_flag = True
            elif '⚠️' in str(status):
                warn_flag = True

            if debt_flag:
                s = 'background-color: rgba(239,68,68,0.1); color: #fca5a5'
            elif warn_flag:
                s = 'background-color: rgba(234,179,8,0.08); color: #fde68a'
            else:
                s = ''
            return [s] * len(row)

        st.dataframe(view_df.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("ℹ️ База пуста. Зарегистрируйте первого ученика.")


# ─────────────────────────────────────────────
# СТРАНИЦА: ПОСЕЩАЕМОСТЬ
# ─────────────────────────────────────────────

elif page == "📅 Посещаемость":
    st.title("Журнал тренировок")

    if not df.empty:
        col_date, col_info = st.columns([2, 3])
        with col_date:
            target_date = st.date_input("📆 Дата тренировки", value=today)
        target_date_str = target_date.strftime("%Y-%m-%d")

        # Текущие отметки на выбранную дату
        already_present = []
        for idx, row in df.iterrows():
            visits = parse_visits(row['Посещения'])
            if target_date_str in visits:
                already_present.append(row['Имя ученика'])

        with col_info:
            st.markdown(f"""
            <div class="stat-card" style="margin-top:28px">
                📊 На эту дату отмечено: <b>{len(already_present)}</b> из <b>{len(df)}</b> учеников
            </div>""", unsafe_allow_html=True)

        st.divider()

        # Отображаем список с предупреждением о нулевом балансе
        student_list = sorted(df['Имя ученика'].dropna().unique())

        # Предупреждения: у кого баланс закончится после этой тренировки
        warnings = {}
        for _, row in df.iterrows():
            name = row['Имя ученика']
            if row['Тип оплаты'] == 'Разовая':
                bal = int(row['Баланс занятий'])
                if bal <= 0 and name not in already_present:
                    warnings[name] = f"⚠️ Баланс: {bal} занятий — нет средств"
                elif bal == 1 and name not in already_present:
                    warnings[name] = "⚠️ Последнее занятие!"

        if warnings:
            st.warning("⚠️ **Внимание:** у следующих учеников заканчивается или закончился баланс:")
            for name, msg in warnings.items():
                st.markdown(f"— **{name}**: {msg}")

        selected_students = st.multiselect(
            "✅ Отметьте присутствующих:",
            student_list,
            default=already_present,
            help="Выберите всех, кто пришёл на тренировку"
        )

        # Показываем, какие изменения произойдут
        added = [s for s in selected_students if s not in already_present]
        removed = [s for s in already_present if s not in selected_students]

        if added or removed:
            preview_col1, preview_col2 = st.columns(2)
            with preview_col1:
                if added:
                    st.markdown("**➕ Будут добавлены:**")
                    for s in added:
                        row = df[df['Имя ученика'] == s].iloc[0]
                        note = ""
                        if row['Тип оплаты'] == 'Разовая':
                            bal = int(row['Баланс занятий'])
                            if bal <= 0:
                                note = f' <span class="debt-chip visit-chip">⚠️ баланс {bal}</span>'
                            else:
                                note = f' <span class="visit-chip">−1 занятие → {bal - 1}</span>'
                        st.markdown(f"• {s}{note}", unsafe_allow_html=True)
            with preview_col2:
                if removed:
                    st.markdown("**➖ Будут убраны:**")
                    for s in removed:
                        row = df[df['Имя ученика'] == s].iloc[0]
                        note = ""
                        if row['Тип оплаты'] == 'Разовая':
                            bal = int(row['Баланс занятий'])
                            note = f' <span class="visit-chip">+1 занятие → {bal + 1}</span>'
                        st.markdown(f"• {s}{note}", unsafe_allow_html=True)

        if st.button("💾 Сохранить посещаемость", type="primary"):
            blocked = []
            for idx in df.index:
                student_name = df.at[idx, 'Имя ученика']
                pay_type = df.at[idx, 'Тип оплаты']
                visits = parse_visits(df.at[idx, 'Посещения'])

                is_selected = student_name in selected_students
                was_present = target_date_str in visits

                if is_selected and not was_present:
                    # Проверка для разовых: не добавляем если баланс <= 0
                    if pay_type == 'Разовая':
                        bal = int(df.at[idx, 'Баланс занятий'])
                        if bal <= 0:
                            blocked.append(student_name)
                            continue  # Пропускаем — баланс пуст
                        df.at[idx, 'Баланс занятий'] = bal - 1

                    visits.append(target_date_str)

                elif not is_selected and was_present:
                    visits.remove(target_date_str)
                    # Возвращаем занятие только если оно было ранее списано
                    if pay_type == 'Разовая':
                        df.at[idx, 'Баланс занятий'] = int(df.at[idx, 'Баланс занятий']) + 1

                df.at[idx, 'Посещения'] = visits_to_str(visits)

            save_data(df)

            if blocked:
                st.warning(f"⚠️ Следующие ученики **не добавлены** (баланс исчерпан): {', '.join(blocked)}")
            st.success(f"✅ Посещаемость за {target_date_str} сохранена!")
            st.rerun()

        st.divider()

        # Статистика посещений за текущий месяц
        st.subheader(f"📊 Статистика за {today.strftime('%B %Y')}")
        month_prefix = today.strftime("%Y-%m")

        stats_rows = []
        for _, row in df.iterrows():
            visits = parse_visits(row['Посещения'])
            month_visits = [v for v in visits if v.startswith(month_prefix)]
            total_visits = len(visits)
            stats_rows.append({
                'Имя': row['Имя ученика'],
                'Тип': row['Тип оплаты'],
                'За месяц': len(month_visits),
                'Всего': total_visits,
                'Баланс': int(row['Баланс занятий']) if row['Тип оплаты'] == 'Разовая' else '—',
                'Последнее посещение': max(visits) if visits else '—',
            })

        stats_df = pd.DataFrame(stats_rows).sort_values('За месяц', ascending=False)
        stats_df.index = range(1, len(stats_df) + 1)
        st.dataframe(stats_df, use_container_width=True)

    else:
        st.info("ℹ️ База пуста.")


# ─────────────────────────────────────────────
# СТРАНИЦА: ИСТОРИЯ ОПЛАТ
# ─────────────────────────────────────────────

elif page == "📋 История оплат":
    st.title("История платежей")

    payments = load_payments()

    # Фильтры
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_name = st.text_input("🔍 Ученик", placeholder="Поиск по имени...")
    with col_f2:
        filter_type = st.selectbox("Тип", ["Все", "Абонемент", "Разовая", "Корректировка"])
    with col_f3:
        period_options = ["Все время", "Этот месяц", "Прошлый месяц", "Последние 30 дней"]
        filter_period = st.selectbox("Период", period_options)

    if not payments.empty:
        payments['Дата'] = pd.to_datetime(payments['Дата'], errors='coerce')
        view_pay = payments.copy()

        if filter_name.strip():
            view_pay = view_pay[view_pay['Имя ученика'].astype(str).str.contains(filter_name.strip(), case=False)]

        if filter_type != "Все":
            view_pay = view_pay[view_pay['Тип'] == filter_type]

        if filter_period == "Этот месяц":
            view_pay = view_pay[view_pay['Дата'].dt.month == today.month]
        elif filter_period == "Прошлый месяц":
            last_month = (today.replace(day=1) - timedelta(days=1))
            view_pay = view_pay[view_pay['Дата'].dt.month == last_month.month]
        elif filter_period == "Последние 30 дней":
            view_pay = view_pay[view_pay['Дата'] >= pd.Timestamp(today - timedelta(days=30))]

        view_pay = view_pay.sort_values('Дата', ascending=False)
        total_period = int(view_pay['Сумма'].sum())

        m1, m2 = st.columns(2)
        m1.metric("Платежей за период", len(view_pay))
        m2.metric("Сумма за период", f"{total_period:,} ₽")

        view_pay['Дата'] = view_pay['Дата'].dt.strftime('%Y-%m-%d')
        view_pay.index = range(1, len(view_pay) + 1)
        st.dataframe(view_pay, use_container_width=True)
    else:
        st.info("ℹ️ История оплат пуста. Платежи появятся после первой оплаты.")


# ─────────────────────────────────────────────
# СТРАНИЦА: РЕГИСТРАЦИЯ
# ─────────────────────────────────────────────

elif page == "➕ Регистрация":
    st.title("Новый ученик")

    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("ФИО ученика *").strip()
            dob = st.date_input("Дата рождения", value=date(2015, 1, 1),
                                min_value=date(1990, 1, 1), max_value=today)
            parent = st.text_input("ФИО родителя")
            phone = st.text_input("Телефон", placeholder="+7 999 000-00-00")

        with col2:
            pay_type = st.radio("Тип оплаты", ["Абонемент", "Разовая"], horizontal=True)
            st.divider()

            if pay_type == "Абонемент":
                paid = st.date_input("Оплачено до", value=get_end_of_month(today))
                price = st.number_input("Стоимость абонемента (₽)", min_value=0,
                                        value=DEFAULT_PRICE_MONTH, step=100)
                balance = 0
                st.info(f"💳 Абонемент до {paid}")
            else:
                paid = None
                balance = st.number_input("Количество занятий", min_value=1, value=4, step=1)
                price = int(balance) * PRICE_PER_SESSION
                st.info(f"💳 {int(balance)} занятий × {PRICE_PER_SESSION} ₽ = **{price} ₽**")

        submitted = st.form_submit_button("✅ СОХРАНИТЬ", use_container_width=True)
        if submitted:
            name_clean = name.strip()
            if not name_clean:
                st.error("❌ Введите имя ученика!")
            elif not df.empty and name_clean.lower() in df['Имя ученика'].astype(str).str.strip().str.lower().values:
                st.warning(f"⚠️ Ученик «{name_clean}» уже есть в базе!")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': name_clean,
                    'Дата рождения': dob,
                    'ФИО родителя': parent.strip(),
                    'Телефон': phone.strip(),
                    'Тип оплаты': pay_type,
                    'Оплачено до': paid,
                    'Баланс занятий': int(balance),
                    'Сумма': int(price),
                    'Посещения': ''
                }])
                save_df = df.drop(columns=['Должник'], errors='ignore')
                save_df = pd.concat([save_df, new_row], ignore_index=True)
                save_data(save_df)

                # Логируем первый платёж
                if price > 0:
                    desc = (f"Абонемент до {paid}" if pay_type == "Абонемент"
                            else f"Куплено {int(balance)} занятий")
                    log_payment(name_clean, pay_type, f"Регистрация: {desc}", int(price))

                st.success(f"✅ Ученик «{name_clean}» добавлен!")
                st.rerun()


# ─────────────────────────────────────────────
# СТРАНИЦА: ОПЛАТА
# ─────────────────────────────────────────────

elif page == "⚙️ Оплата":
    st.title("Управление и оплата")

    if not df.empty:
        student_list = sorted(df['Имя ученика'].dropna().unique())
        student = st.selectbox("👤 Выберите ученика", student_list)

        if student:
            idx = df[df['Имя ученика'] == student].index[0]
            row = df.loc[idx]
            current_type = row['Тип оплаты']

            # Карточка ученика
            visits_all = parse_visits(row['Посещения'])
            month_visits = [v for v in visits_all if v.startswith(today.strftime("%Y-%m"))]

            st.markdown(f"""
            <div class="stat-card">
                <b>{student}</b> &nbsp;|&nbsp; {row['ФИО родителя'] or '—'} &nbsp;|&nbsp; {row['Телефон'] or '—'}<br>
                Тип оплаты: <b>{current_type}</b> &nbsp;|&nbsp;
                Посещений в этом месяце: <b>{len(month_visits)}</b> &nbsp;|&nbsp;
                Всего: <b>{len(visits_all)}</b>
            </div>""", unsafe_allow_html=True)

            st.divider()
            tab_pay, tab_switch, tab_correct, tab_delete = st.tabs(
                ["💳 Оплата", "🔄 Смена типа", "✏️ Корректировка", "🗑 Удалить"])

            # ── TAB: ОПЛАТА ──
            with tab_pay:
                if current_type == "Абонемент":
                    val = row['Оплачено до']
                    if val and not (isinstance(val, float) and pd.isna(val)):
                        st.info(f"Текущий абонемент оплачен до: **{val}**")
                    else:
                        st.warning("Абонемент не оплачен")

                    col1, col2 = st.columns(2)
                    with col1:
                        new_paid = st.date_input("Продлить до", value=get_end_of_month(today))
                    with col2:
                        new_price = st.number_input("Сумма оплаты (₽)", min_value=0,
                                                    value=int(row['Сумма']) or DEFAULT_PRICE_MONTH, step=100)

                    if st.button("✅ Подтвердить оплату абонемента", type="primary"):
                        df.at[idx, 'Оплачено до'] = new_paid
                        df.at[idx, 'Сумма'] = int(new_price)
                        save_data(df)
                        log_payment(student, 'Абонемент', f"Абонемент до {new_paid}", int(new_price))
                        st.success(f"✅ Абонемент продлён до {new_paid}!")
                        st.rerun()

                else:  # Разовая
                    cur_balance = int(row['Баланс занятий'])
                    col1, col2 = st.columns(2)
                    with col1:
                        balance_color = "#34d399" if cur_balance > 0 else "#f87171"
                        st.markdown(f"""
                        <div class="stat-card">
                            <b>Остаток занятий</b><br>
                            <span style="font-size:2rem;color:{balance_color};font-family:Rajdhani">{cur_balance}</span>
                        </div>""", unsafe_allow_html=True)
                        add_sessions = st.number_input("Добавить занятий", min_value=1, value=4, step=1)
                    with col2:
                        pay_amount = int(add_sessions) * PRICE_PER_SESSION
                        st.metric("К оплате", f"{pay_amount} ₽")
                        st.metric("Баланс после оплаты", f"{cur_balance + int(add_sessions)} занятий")

                    if st.button("✅ Подтвердить оплату занятий", type="primary"):
                        new_bal = cur_balance + int(add_sessions)
                        df.at[idx, 'Баланс занятий'] = new_bal
                        df.at[idx, 'Сумма'] = int(add_sessions) * PRICE_PER_SESSION  # Сумма последней покупки
                        save_data(df)
                        log_payment(student, 'Разовая',
                                    f"Куплено {int(add_sessions)} занятий (баланс: {new_bal})", pay_amount)
                        st.success(f"✅ Добавлено {int(add_sessions)} занятий. Новый баланс: {new_bal}")
                        st.rerun()

            # ── TAB: СМЕНА ТИПА ──
            with tab_switch:
                opposite = "Разовая" if current_type == "Абонемент" else "Абонемент"
                st.warning(f"Текущий тип: **{current_type}** → будет изменён на: **{opposite}**")

                if opposite == "Разовая":
                    init_balance = st.number_input("Начальный баланс занятий", min_value=0, value=0, step=1)
                    init_price = int(init_balance) * PRICE_PER_SESSION
                    if init_balance > 0:
                        st.info(f"К оплате при смене: {init_price} ₽")
                else:
                    init_paid = st.date_input("Оплатить до", value=get_end_of_month(today))
                    init_price = st.number_input("Стоимость абонемента", min_value=0,
                                                 value=DEFAULT_PRICE_MONTH, step=100)

                if st.button("🔄 Изменить тип оплаты"):
                    df.at[idx, 'Тип оплаты'] = opposite
                    if opposite == "Разовая":
                        df.at[idx, 'Баланс занятий'] = int(init_balance)
                        df.at[idx, 'Оплачено до'] = None
                        df.at[idx, 'Сумма'] = int(init_price)
                    else:
                        df.at[idx, 'Оплачено до'] = init_paid
                        df.at[idx, 'Баланс занятий'] = 0
                        df.at[idx, 'Сумма'] = int(init_price)
                    save_data(df)
                    if init_price > 0:
                        log_payment(student, 'Корректировка', f"Смена типа → {opposite}", int(init_price))
                    st.success(f"✅ Тип изменён на {opposite}")
                    st.rerun()

            # ── TAB: КОРРЕКТИРОВКА ──
            with tab_correct:
                st.info("Используйте для исправления ошибок в данных без записи в историю.")
                corr_col1, corr_col2 = st.columns(2)
                with corr_col1:
                    if current_type == "Абонемент":
                        corr_date = st.date_input("Исправить дату оплаты",
                                                  value=row['Оплачено до'] if row['Оплачено до'] else today)
                        corr_price = st.number_input("Исправить сумму", min_value=0,
                                                     value=int(row['Сумма']), step=100)
                    else:
                        corr_balance = st.number_input("Установить баланс занятий",
                                                       value=int(row['Баланс занятий']), step=1)
                with corr_col2:
                    corr_name = st.text_input("Исправить имя", value=student)
                    corr_phone = st.text_input("Исправить телефон", value=str(row['Телефон'] or ''))
                    corr_parent = st.text_input("Исправить ФИО родителя", value=str(row['ФИО родителя'] or ''))

                corr_reason = st.text_input("Причина корректировки (для лога)", placeholder="Например: ошибка ввода")

                if st.button("💾 Сохранить корректировку"):
                    df.at[idx, 'Имя ученика'] = corr_name.strip()
                    df.at[idx, 'Телефон'] = corr_phone.strip()
                    df.at[idx, 'ФИО родителя'] = corr_parent.strip()
                    if current_type == "Абонемент":
                        df.at[idx, 'Оплачено до'] = corr_date
                        df.at[idx, 'Сумма'] = int(corr_price)
                    else:
                        df.at[idx, 'Баланс занятий'] = int(corr_balance)
                    save_data(df)
                    reason_str = corr_reason.strip() or 'без причины'
                    log_payment(student, 'Корректировка', f"Ручная правка: {reason_str}", 0)
                    st.success("✅ Данные скорректированы!")
                    st.rerun()

            # ── TAB: УДАЛЕНИЕ ──
            with tab_delete:
                st.error(f"⚠️ Вы собираетесь удалить ученика **{student}** со всей историей посещений.")
                confirm = st.text_input("Введите имя ученика для подтверждения:")
                if st.button("🗑 Удалить безвозвратно", type="primary"):
                    if confirm.strip().lower() == student.lower():
                        save_df = df.drop(columns=['Должник'], errors='ignore')
                        save_df = save_df[save_df['Имя ученика'] != student]
                        save_data(save_df)
                        log_payment(student, 'Корректировка', 'Ученик удалён из базы', 0)
                        st.success(f"✅ Ученик «{student}» удалён.")
                        st.rerun()
                    else:
                        st.error("❌ Имя не совпадает. Удаление отменено.")
    else:
        st.info("ℹ️ База пуста.")
