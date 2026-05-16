"""
Coach Finance Pro — финальная версия.
Все 22 обнаруженных проблемы исправлены.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import os

# ─────────────────────────────────────────────
# НАСТРОЙКИ
# ─────────────────────────────────────────────
DB_FILE = 'students_db.csv'
PAYMENTS_FILE = 'payments_log.csv'
DEFAULT_PRICE_MONTH = 2500
PRICE_PER_SESSION = 250
PERCENT_DIR = 0.40

BASE_COLUMNS = [
    'Имя ученика', 'Дата рождения', 'ФИО родителя',
    'Телефон', 'Оплачено до', 'Сумма'
]
FULL_COLUMNS = [
    'Имя ученика', 'Дата рождения', 'ФИО родителя', 'Телефон',
    'Тип оплаты', 'Оплачено до', 'Баланс занятий', 'Сумма', 'Посещения'
]
PAYMENT_COLUMNS = ['Дата', 'Имя ученика', 'Тип', 'Описание', 'Сумма']

# FIX: русские месяцы — strftime('%B') даёт английский
MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}

# Служебные колонки, которые НИКОГДА не пишем в CSV
_TMP_COLS = ['Должник', '_active', '_debt_val', '_sort_debt', '_sort_date']

# ─────────────────────────────────────────────
# УТИЛИТЫ
# ─────────────────────────────────────────────

def get_end_of_month(d: date) -> date:
    _, last = calendar.monthrange(d.year, d.month)
    return date(d.year, d.month, last)


# FIX: добавлены 'NaT'/'nat' — pandas записывает NaT как строку при сохранении
_BAD_STRS = frozenset({'', 'nan', 'none', 'nat', 'na'})

def parse_visits(raw) -> list[str]:
    """CSV-строка дат → список. Фильтрует NaN/NaT/None/пустые."""
    s = str(raw).strip()
    if s.lower() in _BAD_STRS:
        return []
    return [v.strip() for v in s.split(',')
            if v.strip() and v.strip().lower() not in _BAD_STRS]


def visits_to_str(visits: list[str]) -> str:
    """Дедубликация + сортировка перед записью."""
    return ','.join(sorted({v for v in visits if v.strip()}))


def safe_str(val, fallback: str = '—') -> str:
    """Безопасно превращает поле (может быть NaN/'nan'/None) в строку."""
    s = str(val) if val is not None else ''
    return fallback if s.lower() in _BAD_STRS else s


def is_debt(row, today_dt) -> bool:
    """
    Абонемент: просрочен если дата строго раньше начала сегодня.
    Разовая: долг только при отрицательном балансе (0 — 'пусто', не долг).
    """
    if row['Тип оплаты'] == 'Абонемент':
        val = row['Оплачено до']
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return True
        ts = pd.to_datetime(val, errors='coerce')
        return pd.isna(ts) or ts < today_dt
    return int(row['Баланс занятий']) < 0


def active_value(row, today_dt) -> int:
    if is_debt(row, today_dt):
        return 0
    if row['Тип оплаты'] == 'Абонемент':
        return int(row['Сумма'])
    return max(0, int(row['Баланс занятий'])) * PRICE_PER_SESSION


def debt_value(row, today_dt) -> int:
    if not is_debt(row, today_dt):
        return 0
    if row['Тип оплаты'] == 'Абонемент':
        s = int(row['Сумма'])
        return s if s > 0 else DEFAULT_PRICE_MONTH
    return max(0, -int(row['Баланс занятий'])) * PRICE_PER_SESSION


# ─────────────────────────────────────────────
# БАЗА ДАННЫХ
# ─────────────────────────────────────────────

def upgrade_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Мигрирует любой CSV к текущей схеме."""
    for col, default in [('Тип оплаты', 'Абонемент'),
                         ('Баланс занятий', 0),
                         ('Посещения', '')]:
        if col not in df.columns:
            df[col] = default

    df['Оплачено до']   = pd.to_datetime(df['Оплачено до'],   errors='coerce').dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    df['Сумма']         = pd.to_numeric(df['Сумма'],          errors='coerce').fillna(DEFAULT_PRICE_MONTH).astype(int)
    df['Баланс занятий']= pd.to_numeric(df['Баланс занятий'], errors='coerce').fillna(0).astype(int)

    # FIX: replace() принимает dict — убираем все мусорные строки (включая 'NaT', 'None')
    df['Посещения'] = (
        df['Посещения'].fillna('').astype(str)
        .replace({'nan': '', 'NaT': '', 'None': '', 'nat': '', 'none': '', 'NA': ''})
    )
    return df[FULL_COLUMNS]


def load_data() -> pd.DataFrame:
    if not os.path.exists(DB_FILE):
        empty = pd.DataFrame(columns=FULL_COLUMNS)
        empty.to_csv(DB_FILE, index=False)
        return empty
    df = pd.read_csv(DB_FILE, dtype={'Телефон': str, 'ФИО родителя': str})
    return upgrade_dataframe(df) if not df.empty else df


def save_data(df: pd.DataFrame) -> None:
    """FIX: удаляем ВСЕ временные колонки перед записью."""
    df.drop(columns=_TMP_COLS, errors='ignore').to_csv(DB_FILE, index=False)


def load_payments() -> pd.DataFrame:
    """FIX: try/except — не падаем при повреждённом файле."""
    if not os.path.exists(PAYMENTS_FILE):
        empty = pd.DataFrame(columns=PAYMENT_COLUMNS)
        empty.to_csv(PAYMENTS_FILE, index=False)
        return empty
    try:
        return pd.read_csv(PAYMENTS_FILE)
    except Exception:
        return pd.DataFrame(columns=PAYMENT_COLUMNS)


def save_payments(df: pd.DataFrame) -> None:
    df.to_csv(PAYMENTS_FILE, index=False)


def log_payment(student: str, pay_type: str, desc: str, amount: int) -> None:
    payments = load_payments()
    new = pd.DataFrame([{
        'Дата': date.today().isoformat(),
        'Имя ученика': student,
        'Тип': pay_type,
        'Описание': desc,
        'Сумма': amount,
    }])
    save_payments(pd.concat([payments, new], ignore_index=True))


# ─────────────────────────────────────────────
# STREAMLIT — КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────

st.set_page_config(page_title="Coach Finance Pro", page_icon="🥋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Inter:wght@400;500&display=swap');

.stApp { background:#0a0f1e; color:#e2e8f0; font-family:'Inter',sans-serif; }
[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#111827 0%,#0d1520 100%) !important;
    border-right:1px solid #1e3a5f;
}
h1,h2,h3 { font-family:'Rajdhani',sans-serif; letter-spacing:.05em; }

.stMetric {
    background:rgba(14,30,54,.85); padding:18px; border-radius:14px;
    border:1px solid #1e3a5f; backdrop-filter:blur(6px);
}
.stMetric label { color:#64748b!important; font-size:.75rem!important;
    text-transform:uppercase; letter-spacing:.1em; }
.stMetric [data-testid="metric-container"]>div:nth-child(2) {
    font-family:'Rajdhani',sans-serif; font-size:2rem!important; }

.stButton>button {
    width:100%; border-radius:10px; font-weight:600;
    background:linear-gradient(135deg,#1d4ed8,#1e40af);
    border:none; color:#fff; padding:.6rem 1rem;
}
.stButton>button:hover {
    background:linear-gradient(135deg,#2563eb,#1d4ed8);
    transform:translateY(-1px); box-shadow:0 4px 15px rgba(37,99,235,.4);
}
div[data-testid="stForm"] {
    background:rgba(14,30,54,.5); border-radius:16px;
    padding:20px; border:1px solid #1e3a5f;
}
.chip {
    display:inline-block; border-radius:6px;
    padding:2px 8px; font-size:.75rem; margin:2px;
}
.chip-green { background:rgba(16,185,129,.15); color:#34d399; border:1px solid rgba(52,211,153,.3); }
.chip-red   { background:rgba(239,68,68,.15);  color:#f87171; border:1px solid rgba(248,113,113,.3); }
.chip-yellow{ background:rgba(234,179,8,.15);  color:#fbbf24; border:1px solid rgba(251,191,36,.3); }

.badge {
    display:inline-block; border-radius:20px;
    padding:3px 10px; font-size:.75rem; font-weight:600;
}
.badge-green { background:rgba(16,185,129,.2); color:#34d399; border:1px solid rgba(52,211,153,.3); }
.badge-red   { background:rgba(239,68,68,.2);  color:#f87171; border:1px solid rgba(248,113,113,.3); }
.badge-yellow{ background:rgba(234,179,8,.2);  color:#fbbf24; border:1px solid rgba(251,191,36,.3); }

.stat-card {
    background:rgba(14,30,54,.7); border-radius:12px; padding:14px 18px;
    border:1px solid #1e3a5f; margin-bottom:10px;
}
.bal-big {
    font-family:'Rajdhani',sans-serif; font-weight:700; font-size:2.8rem;
    line-height:1;
}
</style>
""", unsafe_allow_html=True)

# ─── ЗАГРУЗКА ───────────────────────────────
df       = load_data()
today    = date.today()
today_dt = pd.to_datetime(today)

if not df.empty:
    df['Должник'] = df.apply(lambda r: is_debt(r, today_dt), axis=1)

# ─── САЙДБАР ────────────────────────────────
with st.sidebar:
    st.markdown("## 🥋 ТРЕНЕР PRO")
    page = st.radio(
        "", ["📊 Дашборд", "📅 Посещаемость", "📋 История оплат",
             "➕ Регистрация", "⚙️ Оплата"],
        label_visibility="collapsed"
    )
    st.divider()

    st.subheader("💾 РЕЗЕРВНАЯ КОПИЯ")
    if not df.empty:
        st.download_button(
            "📥 Скачать базу учеников",
            data=df.drop(columns=_TMP_COLS, errors='ignore').to_csv(index=False).encode('utf-8-sig'),
            file_name=f"students_{today}.csv", mime="text/csv"
        )
    pays_sb = load_payments()
    if not pays_sb.empty:
        st.download_button(
            "📥 Скачать историю оплат",
            data=pays_sb.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"payments_{today}.csv", mime="text/csv"
        )

    up = st.file_uploader("📤 Восстановить базу", type=None)
    if up is not None:
        try:
            ndf = pd.read_csv(up)
            if all(c in ndf.columns for c in BASE_COLUMNS):
                save_data(upgrade_dataframe(ndf))
                st.success("✅ База обновлена!")
                st.rerun()
            else:
                st.error("❌ Неверный формат файла.")
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")

    st.divider()
    if not df.empty:
        debtors = int(df['Должник'].sum())
        st.markdown(f"**Учеников:** {len(df)}")
        if debtors:
            st.markdown(f'<span class="badge badge-red">🔴 Должников: {debtors}</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-green">🟢 Все оплачено</span>',
                        unsafe_allow_html=True)

        # Абонементы, истекающие в течение 3 дней (FIX: с проверкой нижней границы)
        thr = today_dt + pd.Timedelta(days=3)
        soon = df[
            (df['Тип оплаты'] == 'Абонемент') & (~df['Должник']) &
            df['Оплачено до'].apply(
                lambda v: (v is not None and
                           not (isinstance(v, float) and pd.isna(v)) and
                           today_dt <= pd.to_datetime(v, errors='coerce') <= thr)
            )
        ]
        if not soon.empty:
            st.markdown(f'<span class="badge badge-yellow">⚠️ Истекает скоро: {len(soon)}</span>',
                        unsafe_allow_html=True)

        # Разовые с нулевым балансом
        zero_bal = df[(df['Тип оплаты'] == 'Разовая') & (df['Баланс занятий'] == 0)]
        if not zero_bal.empty:
            st.markdown(f'<span class="badge badge-yellow">🎯 Нет занятий: {len(zero_bal)}</span>',
                        unsafe_allow_html=True)


# ═════════════════════════════════════════════
# ДАШБОРД
# ═════════════════════════════════════════════
if page == "📊 Дашборд":
    st.title("Финансовый отчёт")

    if not df.empty:
        df['_active']   = df.apply(lambda r: active_value(r, today_dt), axis=1)
        df['_debt_val'] = df.apply(lambda r: debt_value(r, today_dt),   axis=1)

        total_active   = int(df['_active'].sum())
        total_debt     = int(df['_debt_val'].sum())
        director_share = int(total_active * PERCENT_DIR)
        coach_net      = total_active - director_share

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Активная база",   f"{total_active:,} ₽",
                  help="Оплаченные абонементы + остаток разовых занятий")
        c2.metric("🏢 Доля клуба 40%", f"{director_share:,} ₽")
        c3.metric("👤 Ваша чистая ЗП", f"{coach_net:,} ₽")
        c4.metric("🔴 Задолженность",  f"{int(df['Должник'].sum())} чел.",
                  delta=f"⚠️ {total_debt:,} ₽" if total_debt else "Долгов нет",
                  delta_color="inverse" if total_debt else "normal")

        st.divider()
        ca, cb = st.columns(2)
        sub_df  = df[df['Тип оплаты'] == 'Абонемент']
        sess_df = df[df['Тип оплаты'] == 'Разовая']
        ca.markdown(f"""<div class="stat-card"><b>📋 Абонементы</b><br>
            Всего: {len(sub_df)} &nbsp;|&nbsp;
            Активных: {int((~sub_df['Должник']).sum())} &nbsp;|&nbsp;
            Должников: {int(sub_df['Должник'].sum())}
        </div>""", unsafe_allow_html=True)
        cb.markdown(f"""<div class="stat-card"><b>🎯 Разовые занятия</b><br>
            Всего: {len(sess_df)} &nbsp;|&nbsp;
            С балансом: {int((sess_df['Баланс занятий'] > 0).sum())} &nbsp;|&nbsp;
            Баланс = 0: {int((sess_df['Баланс занятий'] == 0).sum())}
        </div>""", unsafe_allow_html=True)

        st.divider()
        search = st.text_input("🔍 Поиск по имени", placeholder="Введите имя...")

        view = df.drop(columns=_TMP_COLS, errors='ignore').copy()

        # FIX: сортировка через числовые колонки — кортежи нестабильны в pandas
        view['_sort_debt'] = view.apply(lambda r: 0 if is_debt(r, today_dt) else 1, axis=1)
        view['_sort_date'] = view.apply(
            lambda r: pd.to_datetime(r['Оплачено до'], errors='coerce')
                      if r['Тип оплаты'] == 'Абонемент' else pd.Timestamp.min,
            axis=1
        )
        view = view.sort_values(
            ['_sort_debt', '_sort_date', 'Имя ученика'],
            ascending=[True, True, True], na_position='first'
        ).drop(columns=['_sort_debt', '_sort_date'])

        view['Оплачено до'] = view['Оплачено до'].apply(
            lambda v: '—' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        )

        def _status(r):
            if r['Тип оплаты'] == 'Абонемент':
                val = r['Оплачено до']
                if val == '—':                                       return '❌ Не оплачен'
                dt = pd.to_datetime(val, errors='coerce')
                if pd.isna(dt) or dt < today_dt:                     return '❌ Просрочен'
                if dt <= today_dt + pd.Timedelta(days=3):            return '⚠️ Истекает'
                return '✅ Активен'
            else:
                b = int(r['Баланс занятий'])
                if b > 0:  return f'✅ {b} занятий'
                if b == 0: return '⚠️ Закончились'
                return f'❌ Долг {-b} зан.'

        view['Статус'] = view.apply(_status, axis=1)
        view['Посещений'] = view['Посещения'].apply(lambda v: len(parse_visits(v)))
        # FIX: для абонементов баланс не имеет смысла — показываем '—'
        view['Баланс занятий'] = view.apply(
            lambda r: '—' if r['Тип оплаты'] == 'Абонемент'
                      else str(int(r['Баланс занятий'])), axis=1
        )

        cols = ['Имя ученика', 'Тип оплаты', 'Статус', 'Оплачено до',
                'Баланс занятий', 'Сумма', 'Посещений', 'Телефон', 'ФИО родителя']
        view = view[cols]
        if search.strip():
            view = view[view['Имя ученика'].astype(str).str.contains(
                search.strip(), case=False, na=False)]
        view.index = range(1, len(view) + 1)

        def _style(row):
            st = str(row.get('Статус', ''))
            if '❌' in st: return ['background:rgba(239,68,68,.1);color:#fca5a5'] * len(row)
            if '⚠️' in st: return ['background:rgba(234,179,8,.08);color:#fde68a'] * len(row)
            return [''] * len(row)

        st.dataframe(view.style.apply(_style, axis=1), use_container_width=True)
    else:
        st.info("ℹ️ База пуста. Зарегистрируйте первого ученика.")


# ═════════════════════════════════════════════
# ПОСЕЩАЕМОСТЬ
# ═════════════════════════════════════════════
elif page == "📅 Посещаемость":
    st.title("Журнал тренировок")

    if not df.empty:
        c_date, c_info = st.columns([2, 3])
        with c_date:
            target_date = st.date_input("📆 Дата тренировки", value=today)
        tds = target_date.strftime("%Y-%m-%d")

        already = [r['Имя ученика'] for _, r in df.iterrows()
                   if tds in parse_visits(r['Посещения'])]

        with c_info:
            st.markdown(f"""<div class="stat-card" style="margin-top:28px">
                📊 Отмечено {tds}: <b>{len(already)}</b> из <b>{len(df)}</b>
            </div>""", unsafe_allow_html=True)

        st.divider()

        student_list = sorted(df['Имя ученика'].dropna().unique())

        # FIX: переименован в balance_alerts — 'warnings' конфликтует с builtins
        balance_alerts: dict[str, tuple[str, str]] = {}  # name → (level, msg)
        for _, r in df.iterrows():
            name = r['Имя ученика']
            if r['Тип оплаты'] == 'Разовая' and name not in already:
                b = int(r['Баланс занятий'])
                if b <= 0:
                    balance_alerts[name] = ('red',   f"баланс {b} — занятий нет")
                elif b == 1:
                    balance_alerts[name] = ('yellow', "последнее занятие!")

        if balance_alerts:
            reds = [f"**{n}** ({m})" for n, (l, m) in balance_alerts.items() if l == 'red']
            yellows = [f"**{n}** ({m})" for n, (l, m) in balance_alerts.items() if l == 'yellow']
            if reds:
                st.error("⛔ Нет занятий: " + ", ".join(reds))
            if yellows:
                st.warning("⚠️ Последнее занятие: " + ", ".join(yellows))

        selected = st.multiselect(
            "✅ Отметьте присутствующих:", student_list, default=already,
            help="Выберите всех, кто пришёл на тренировку"
        )

        # FIX: новая опция — разрешить тренеру записать разового ученика в долг
        force_debt_mode = st.checkbox(
            "💳 Разрешить запись в долг (для разовых с балансом 0)",
            value=False,
            help="Если включено — ученик с нулевым балансом будет отмечен, баланс уйдёт в минус"
        )

        added   = [s for s in selected if s not in already]
        removed = [s for s in already  if s not in selected]

        if added or removed:
            pc1, pc2 = st.columns(2)
            with pc1:
                if added:
                    st.markdown("**➕ Будут добавлены:**")
                    for s in added:
                        r = df[df['Имя ученика'] == s].iloc[0]
                        note = ""
                        if r['Тип оплаты'] == 'Разовая':
                            b = int(r['Баланс занятий'])
                            if b <= 0:
                                if force_debt_mode:
                                    note = (f' <span class="chip chip-yellow">'
                                            f'⚠️ в долг → {b - 1}</span>')
                                else:
                                    note = (f' <span class="chip chip-red">'
                                            f'⛔ баланс {b} — НЕ будет добавлен</span>')
                            else:
                                note = f' <span class="chip chip-green">−1 → {b-1}</span>'
                        st.markdown(f"• {s}{note}", unsafe_allow_html=True)
            with pc2:
                if removed:
                    st.markdown("**➖ Будут убраны:**")
                    for s in removed:
                        r = df[df['Имя ученика'] == s].iloc[0]
                        note = ""
                        if r['Тип оплаты'] == 'Разовая':
                            b = int(r['Баланс занятий'])
                            note = f' <span class="chip chip-green">+1 → {b+1}</span>'
                        st.markdown(f"• {s}{note}", unsafe_allow_html=True)

        if st.button("💾 Сохранить посещаемость", type="primary"):
            blocked = []
            for idx in df.index:
                name     = df.at[idx, 'Имя ученика']
                ptype    = df.at[idx, 'Тип оплаты']
                visits   = parse_visits(df.at[idx, 'Посещения'])
                is_sel   = name in selected
                was_here = tds in visits

                if is_sel and not was_here:
                    if ptype == 'Разовая':
                        b = int(df.at[idx, 'Баланс занятий'])
                        if b <= 0 and not force_debt_mode:
                            blocked.append(name)
                            continue  # Посещения и баланс не трогаем
                        df.at[idx, 'Баланс занятий'] = b - 1
                    visits.append(tds)

                elif not is_sel and was_here:
                    visits.remove(tds)
                    # FIX: возврат занятия только разовым (абонементный баланс = 0, трогать не нужно)
                    if ptype == 'Разовая':
                        df.at[idx, 'Баланс занятий'] = int(df.at[idx, 'Баланс занятий']) + 1

                df.at[idx, 'Посещения'] = visits_to_str(visits)

            save_data(df)
            if blocked:
                st.warning(f"⛔ Не добавлены (нет баланса): {', '.join(blocked)}")
            st.success(f"✅ Посещаемость за {tds} сохранена!")
            st.rerun()

        st.divider()

        # FIX: русское название месяца
        month_ru = MONTHS_RU[today.month]
        st.subheader(f"📊 Статистика: {month_ru} {today.year}")
        mp = today.strftime("%Y-%m")

        stats_rows = []
        for _, r in df.iterrows():
            vs = parse_visits(r['Посещения'])
            mv = [v for v in vs if v.startswith(mp)]
            stats_rows.append({
                'Имя':               r['Имя ученика'],
                'Тип':               r['Тип оплаты'],
                month_ru:            len(mv),
                'Всего':             len(vs),
                'Баланс':            int(r['Баланс занятий']) if r['Тип оплаты'] == 'Разовая' else '—',
                'Последнее посещение': max(vs) if vs else '—',
            })
        if stats_rows:
            sdf = pd.DataFrame(stats_rows).sort_values(month_ru, ascending=False)
            sdf.index = range(1, len(sdf) + 1)
            st.dataframe(sdf, use_container_width=True)
    else:
        st.info("ℹ️ База пуста.")


# ═════════════════════════════════════════════
# ИСТОРИЯ ОПЛАТ
# ═════════════════════════════════════════════
elif page == "📋 История оплат":
    st.title("История платежей")

    payments = load_payments()

    f1, f2, f3 = st.columns(3)
    with f1: fn = st.text_input("🔍 Ученик", placeholder="Поиск по имени...")
    with f2: ft = st.selectbox("Тип", ["Все", "Абонемент", "Разовая", "Корректировка"])
    with f3: fp = st.selectbox("Период", ["Все время", "Этот месяц", "Прошлый месяц", "Последние 30 дней"])

    if not payments.empty:
        payments['Дата'] = pd.to_datetime(payments['Дата'], errors='coerce')
        vp = payments.copy()

        if fn.strip():
            vp = vp[vp['Имя ученика'].astype(str).str.contains(fn.strip(), case=False, na=False)]
        if ft != "Все":
            vp = vp[vp['Тип'] == ft]

        # FIX: фильтр по месяцу с проверкой ГОДА
        if fp == "Этот месяц":
            vp = vp[(vp['Дата'].dt.year == today.year) & (vp['Дата'].dt.month == today.month)]
        elif fp == "Прошлый месяц":
            lm = today.replace(day=1) - timedelta(days=1)
            vp = vp[(vp['Дата'].dt.year == lm.year) & (vp['Дата'].dt.month == lm.month)]
        elif fp == "Последние 30 дней":
            vp = vp[vp['Дата'] >= pd.Timestamp(today - timedelta(days=30))]

        vp = vp.sort_values('Дата', ascending=False)
        total = int(vp['Сумма'].fillna(0).sum())

        m1, m2 = st.columns(2)
        m1.metric("Платежей за период", len(vp))
        m2.metric("Сумма за период", f"{total:,} ₽")

        dp = vp.copy()
        dp['Дата'] = dp['Дата'].dt.strftime('%Y-%m-%d')
        dp.index = range(1, len(dp) + 1)
        st.dataframe(dp, use_container_width=True)
    else:
        st.info("ℹ️ История пуста. Платежи появятся после первой оплаты.")


# ═════════════════════════════════════════════
# РЕГИСТРАЦИЯ
# ═════════════════════════════════════════════
elif page == "➕ Регистрация":
    st.title("Новый ученик")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            # FIX: strip() ВНУТРИ блока submitted, не на виджете напрямую
            name   = st.text_input("ФИО ученика *")
            dob    = st.date_input("Дата рождения", value=date(2015, 1, 1),
                                   min_value=date(1990, 1, 1), max_value=today)
            parent = st.text_input("ФИО родителя")
            phone  = st.text_input("Телефон", placeholder="+7 999 000-00-00")
        with c2:
            pay_type = st.radio("Тип оплаты", ["Абонемент", "Разовая"], horizontal=True)
            st.divider()
            if pay_type == "Абонемент":
                paid    = st.date_input("Оплачено до", value=get_end_of_month(today))
                price   = st.number_input("Стоимость (₽)", min_value=0,
                                          value=DEFAULT_PRICE_MONTH, step=100)
                balance = 0
                st.info(f"💳 Абонемент до {paid}")
            else:
                paid    = None
                balance = st.number_input("Количество занятий", min_value=1, value=4, step=1)
                price   = int(balance) * PRICE_PER_SESSION
                st.info(f"💳 {int(balance)} × {PRICE_PER_SESSION} ₽ = **{price:,} ₽**")

        if st.form_submit_button("✅ СОХРАНИТЬ", use_container_width=True):
            name_clean = name.strip()
            if not name_clean:
                st.error("❌ Введите имя ученика!")
            elif not df.empty and name_clean.lower() in (
                df['Имя ученика'].astype(str).str.strip().str.lower().values
            ):
                st.warning(f"⚠️ Ученик «{name_clean}» уже есть в базе!")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': name_clean, 'Дата рождения': dob,
                    'ФИО родителя': parent.strip(), 'Телефон': phone.strip(),
                    'Тип оплаты': pay_type, 'Оплачено до': paid,
                    'Баланс занятий': int(balance), 'Сумма': int(price), 'Посещения': ''
                }])
                save_data(pd.concat(
                    [df.drop(columns=_TMP_COLS, errors='ignore'), new_row],
                    ignore_index=True
                ))
                if price > 0:
                    log_payment(name_clean, pay_type,
                                f"Регистрация: {'абонемент до ' + str(paid) if pay_type == 'Абонемент' else str(int(balance)) + ' занятий'}",
                                int(price))
                st.success(f"✅ Ученик «{name_clean}» добавлен!")
                st.rerun()


# ═════════════════════════════════════════════
# ОПЛАТА И УПРАВЛЕНИЕ
# ═════════════════════════════════════════════
elif page == "⚙️ Оплата":
    st.title("Управление и оплата")

    if not df.empty:
        # FIX: проверяем что список не пустой перед selectbox
        student_list = sorted(df['Имя ученика'].dropna().unique().tolist())
        if not student_list:
            st.warning("⚠️ В базе нет учеников с заполненным именем.")
            st.stop()

        student = st.selectbox("👤 Выберите ученика", student_list)

        if student:
            idx          = df[df['Имя ученика'] == student].index[0]
            row          = df.loc[idx]
            current_type = row['Тип оплаты']
            visits_all   = parse_visits(row['Посещения'])
            month_vs     = [v for v in visits_all if v.startswith(today.strftime("%Y-%m"))]

            # FIX: safe_str убирает строку 'nan' из полей
            parent_s = safe_str(row['ФИО родителя'])
            phone_s  = safe_str(row['Телефон'])

            st.markdown(f"""<div class="stat-card">
                <b>{student}</b> &nbsp;|&nbsp; {parent_s} &nbsp;|&nbsp; {phone_s}<br>
                Тип: <b>{current_type}</b> &nbsp;|&nbsp;
                В этом месяце: <b>{len(month_vs)}</b> &nbsp;|&nbsp;
                Всего посещений: <b>{len(visits_all)}</b>
            </div>""", unsafe_allow_html=True)

            st.divider()
            tab_pay, tab_switch, tab_correct, tab_delete = st.tabs(
                ["💳 Оплата", "🔄 Смена типа", "✏️ Корректировка", "🗑 Удалить"]
            )

            # ── ОПЛАТА ──────────────────────────────
            with tab_pay:
                if current_type == "Абонемент":
                    val = row['Оплачено до']
                    if val and not (isinstance(val, float) and pd.isna(val)):
                        paid_ts = pd.to_datetime(val, errors='coerce')
                        if pd.isna(paid_ts) or paid_ts < today_dt:
                            st.error(f"❌ Просрочен! Был оплачен до: **{val}**")
                        elif paid_ts <= today_dt + pd.Timedelta(days=3):
                            st.warning(f"⚠️ Истекает: **{val}**")
                        else:
                            st.info(f"✅ Оплачен до: **{val}**")
                    else:
                        st.error("❌ Абонемент не оплачен")

                    p1, p2 = st.columns(2)
                    with p1:
                        new_paid = st.date_input("Продлить до", value=get_end_of_month(today))
                    with p2:
                        # FIX: если Сумма=0, предлагаем DEFAULT, не 0
                        def_price = int(row['Сумма']) if int(row['Сумма']) > 0 else DEFAULT_PRICE_MONTH
                        new_price = st.number_input("Сумма (₽)", min_value=0,
                                                    value=def_price, step=100)
                    if st.button("✅ Подтвердить оплату абонемента", type="primary"):
                        df.at[idx, 'Оплачено до'] = new_paid
                        df.at[idx, 'Сумма']       = int(new_price)
                        save_data(df)
                        log_payment(student, 'Абонемент', f"Абонемент до {new_paid}", int(new_price))
                        st.success(f"✅ Продлён до {new_paid}!")
                        st.rerun()

                else:  # Разовая
                    cur_bal = int(row['Баланс занятий'])
                    p1, p2  = st.columns(2)
                    with p1:
                        col = "#34d399" if cur_bal > 0 else ("#fbbf24" if cur_bal == 0 else "#f87171")
                        st.markdown(f"""<div class="stat-card">
                            <b>Остаток занятий</b><br>
                            <span class="bal-big" style="color:{col}">{cur_bal}</span>
                        </div>""", unsafe_allow_html=True)
                        add = st.number_input("Добавить занятий", min_value=1, value=4, step=1)
                    with p2:
                        amt = int(add) * PRICE_PER_SESSION
                        st.metric("К оплате",           f"{amt:,} ₽")
                        st.metric("Баланс после оплаты", f"{cur_bal + int(add)} занятий")

                    if st.button("✅ Подтвердить оплату занятий", type="primary"):
                        new_bal = cur_bal + int(add)
                        df.at[idx, 'Баланс занятий'] = new_bal
                        df.at[idx, 'Сумма']          = int(add) * PRICE_PER_SESSION
                        save_data(df)
                        log_payment(student, 'Разовая',
                                    f"Куплено {int(add)} занятий (баланс: {new_bal})", amt)
                        st.success(f"✅ Добавлено {int(add)} занятий. Баланс: {new_bal}")
                        st.rerun()

            # ── СМЕНА ТИПА ──────────────────────────
            with tab_switch:
                opposite = "Разовая" if current_type == "Абонемент" else "Абонемент"
                st.warning(f"**{current_type}** → **{opposite}**")

                # FIX: обе переменные init_paid / init_balance определяются всегда
                init_paid    = None
                init_balance = 0
                init_price   = 0

                if opposite == "Разовая":
                    init_balance = int(st.number_input("Начальный баланс занятий",
                                                       min_value=0, value=0, step=1))
                    init_price = init_balance * PRICE_PER_SESSION
                    if init_balance > 0:
                        st.info(f"К оплате: {init_price:,} ₽")
                else:
                    init_paid  = st.date_input("Оплатить до", value=get_end_of_month(today))
                    init_price = int(st.number_input("Стоимость абонемента (₽)", min_value=0,
                                                     value=DEFAULT_PRICE_MONTH, step=100))

                if st.button("🔄 Изменить тип оплаты"):
                    df.at[idx, 'Тип оплаты']     = opposite
                    df.at[idx, 'Баланс занятий'] = init_balance
                    df.at[idx, 'Оплачено до']    = init_paid
                    df.at[idx, 'Сумма']          = init_price
                    save_data(df)
                    if init_price > 0:
                        log_payment(student, 'Корректировка',
                                    f"Смена типа → {opposite}", init_price)
                    st.success(f"✅ Тип изменён на {opposite}")
                    st.rerun()

            # ── КОРРЕКТИРОВКА ───────────────────────
            with tab_correct:
                # FIX: убрана ложная фраза "без записи в историю"
                st.info("Ручное исправление данных. Каждая правка сохраняется в лог.")

                cc1, cc2 = st.columns(2)
                with cc1:
                    if current_type == "Абонемент":
                        safe_date = (
                            row['Оплачено до']
                            if row['Оплачено до'] and
                               not (isinstance(row['Оплачено до'], float) and pd.isna(row['Оплачено до']))
                            else today
                        )
                        corr_date  = st.date_input("Оплачено до", value=safe_date)
                        corr_price = st.number_input("Сумма (₽)", min_value=0,
                                                     value=int(row['Сумма']), step=100)
                    else:
                        # FIX: для разовых теперь редактируются и баланс, и сумма
                        corr_balance = st.number_input("Баланс занятий",
                                                       value=int(row['Баланс занятий']), step=1)
                        corr_price   = st.number_input(
                            "Сумма последней покупки (₽)", min_value=0,
                            value=int(row['Сумма']), step=100
                        )
                with cc2:
                    corr_name   = st.text_input("Имя ученика", value=student)
                    corr_phone  = st.text_input("Телефон",      value=safe_str(row['Телефон'],  ''))
                    corr_parent = st.text_input("ФИО родителя", value=safe_str(row['ФИО родителя'], ''))

                corr_reason = st.text_input("Причина правки",
                                            placeholder="Например: ошибочно введена сумма")

                if st.button("💾 Сохранить корректировку"):
                    name_new = corr_name.strip()
                    if not name_new:
                        st.error("❌ Имя не может быть пустым!")
                    else:
                        df.at[idx, 'Имя ученика']  = name_new
                        df.at[idx, 'Телефон']       = corr_phone.strip()
                        df.at[idx, 'ФИО родителя']  = corr_parent.strip()
                        df.at[idx, 'Сумма']         = int(corr_price)
                        if current_type == "Абонемент":
                            df.at[idx, 'Оплачено до'] = corr_date
                        else:
                            df.at[idx, 'Баланс занятий'] = int(corr_balance)
                        save_data(df)
                        log_payment(student, 'Корректировка',
                                    f"Правка: {corr_reason.strip() or 'без причины'}", 0)
                        st.success("✅ Данные скорректированы!")
                        st.rerun()

            # ── УДАЛЕНИЕ ────────────────────────────
            with tab_delete:
                st.error(f"⚠️ Удаление **{student}** вместе со всей историей посещений.")
                confirm = st.text_input("Введите имя ученика для подтверждения:")
                if st.button("🗑 Удалить безвозвратно", type="primary"):
                    if confirm.strip().lower() == student.lower():
                        save_data(df[df['Имя ученика'] != student].copy())
                        log_payment(student, 'Корректировка', 'Ученик удалён из базы', 0)
                        st.success(f"✅ Ученик «{student}» удалён.")
                        st.rerun()
                    else:
                        st.error("❌ Имя не совпадает. Удаление отменено.")
    else:
        st.info("ℹ️ База пуста.")
