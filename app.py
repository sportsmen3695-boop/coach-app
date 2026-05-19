"""
Coach Finance Pro — финальная версия + накопление оплат и расширенный бэкап.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import os
import io
import zipfile

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
VISIT_EXPORT_COLUMNS = ['Дата', 'Имя ученика', 'Тип оплаты']

MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}

_TMP_COLS = ['Должник', '_active', '_debt_val', '_sort_debt', '_sort_date']


def get_end_of_month(d: date) -> date:
    _, last = calendar.monthrange(d.year, d.month)
    return date(d.year, d.month, last)


_BAD_STRS = frozenset({'', 'nan', 'none', 'nat', 'na'})


def parse_visits(raw) -> list[str]:
    s = str(raw).strip()
    if s.lower() in _BAD_STRS:
        return []
    return [v.strip() for v in s.split(',')
            if v.strip() and v.strip().lower() not in _BAD_STRS]


def visits_to_str(visits: list[str]) -> str:
    return ','.join(sorted({v for v in visits if v.strip()}))


def safe_str(val, fallback: str = '—') -> str:
    s = str(val) if val is not None else ''
    return fallback if s.lower() in _BAD_STRS else s


def is_debt(row, today_dt) -> bool:
    if row['Тип оплаты'] == 'Абонемент':
        val = row['Оплачено до']
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return True
        ts = pd.to_datetime(val, errors='coerce')
        return pd.isna(ts) or ts < today_dt
    return int(row['Баланс занятий']) < 0


def active_value(row, today_dt) -> int:
    if row['Тип оплаты'] == 'Абонемент':
        if is_debt(row, today_dt):
            return 0
        return int(row['Сумма'])
    # Разовая: всегда возвращаем оплаченное, долг считается отдельно
    return max(0, int(row['Сумма']))


def debt_value(row, today_dt) -> int:
    if not is_debt(row, today_dt):
        return 0
    if row['Тип оплаты'] == 'Абонемент':
        s = int(row['Сумма'])
        return s if s > 0 else DEFAULT_PRICE_MONTH
    return max(0, -int(row['Баланс занятий'])) * PRICE_PER_SESSION


def upgrade_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col, default in [('Тип оплаты', 'Абонемент'),
                         ('Баланс занятий', 0),
                         ('Посещения', '')]:
        if col not in df.columns:
            df[col] = default

    df['Оплачено до'] = pd.to_datetime(df['Оплачено до'], errors='coerce').dt.date
    df['Дата рождения'] = pd.to_datetime(df['Дата рождения'], errors='coerce').dt.date
    df['Сумма'] = pd.to_numeric(df['Сумма'], errors='coerce').fillna(DEFAULT_PRICE_MONTH).astype(int)
    df['Баланс занятий'] = pd.to_numeric(df['Баланс занятий'], errors='coerce').fillna(0).astype(int)
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
    df.drop(columns=_TMP_COLS, errors='ignore').to_csv(DB_FILE, index=False)


def load_payments() -> pd.DataFrame:
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


def update_payment_row(row_idx: int, dt, student: str, pay_type: str, desc: str, amount: int) -> bool:
    payments = load_payments()
    if payments.empty or row_idx not in payments.index:
        return False
    payments.at[row_idx, 'Дата'] = pd.Timestamp(dt).strftime('%Y-%m-%d')
    payments.at[row_idx, 'Имя ученика'] = student.strip()
    payments.at[row_idx, 'Тип'] = pay_type
    payments.at[row_idx, 'Описание'] = desc.strip()
    payments.at[row_idx, 'Сумма'] = int(amount)
    save_payments(payments[PAYMENT_COLUMNS])
    return True


def delete_payment_row(row_idx: int) -> bool:
    payments = load_payments()
    if payments.empty or row_idx not in payments.index:
        return False
    save_payments(payments.drop(index=row_idx).reset_index(drop=True))
    return True


def apply_visit_correction(
    df: pd.DataFrame, idx, new_visits: list[str], adjust_balance: bool,
) -> tuple[int, int]:
    """Возвращает (добавлено дат, убрано дат) для разовых при adjust_balance."""
    old_visits = set(parse_visits(df.at[idx, 'Посещения']))
    new_set = {v for v in new_visits if v.strip()}
    added = len(new_set - old_visits)
    removed = len(old_visits - new_set)
    df.at[idx, 'Посещения'] = visits_to_str(sorted(new_set))
    if adjust_balance and df.at[idx, 'Тип оплаты'] == 'Разовая':
        df.at[idx, 'Баланс занятий'] = int(df.at[idx, 'Баланс занятий']) + removed - added
    return added, removed


def visits_to_dataframe(students: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in students.iterrows():
        for d in parse_visits(r['Посещения']):
            rows.append({
                'Дата': d,
                'Имя ученика': r['Имя ученика'],
                'Тип оплаты': r['Тип оплаты'],
            })
    if not rows:
        return pd.DataFrame(columns=VISIT_EXPORT_COLUMNS)
    return (
        pd.DataFrame(rows)
        .sort_values(['Дата', 'Имя ученика'], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_backup_zip(students: pd.DataFrame, payments: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    stud = students.drop(columns=_TMP_COLS, errors='ignore')
    visits = visits_to_dataframe(stud)
    stamp = date.today().isoformat()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'students_{stamp}.csv', stud.to_csv(index=False))
        pay_df = payments if not payments.empty else pd.DataFrame(columns=PAYMENT_COLUMNS)
        zf.writestr(f'payments_{stamp}.csv', pay_df.to_csv(index=False))
        zf.writestr(f'visits_{stamp}.csv', visits.to_csv(index=False))
    return buf.getvalue()


def restore_students_csv(uploaded) -> tuple[bool, str]:
    try:
        ndf = pd.read_csv(uploaded)
        if not all(c in ndf.columns for c in BASE_COLUMNS):
            return False, 'Нужны колонки: ' + ', '.join(BASE_COLUMNS)
        save_data(upgrade_dataframe(ndf))
        return True, 'База учеников восстановлена (посещения внутри CSV).'
    except Exception as e:
        return False, str(e)


def restore_payments_csv(uploaded) -> tuple[bool, str]:
    try:
        pdf = pd.read_csv(uploaded)
        if not all(c in pdf.columns for c in PAYMENT_COLUMNS):
            return False, 'Неверный формат истории оплат.'
        save_payments(pdf[PAYMENT_COLUMNS])
        return True, 'История оплат восстановлена.'
    except Exception as e:
        return False, str(e)


def restore_backup_zip(uploaded) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(uploaded) as zf:
            names = zf.namelist()
            student_file = next(
                (n for n in names if n.lower().startswith('students') and n.endswith('.csv')),
                None,
            )
            if not student_file:
                return False, 'В архиве нет students_*.csv'
            ndf = pd.read_csv(zf.open(student_file))
            if not all(c in ndf.columns for c in BASE_COLUMNS):
                return False, 'Неверный формат students в архиве.'
            save_data(upgrade_dataframe(ndf))
            parts = ['база учеников']
            pay_file = next(
                (n for n in names if n.lower().startswith('payments') and n.endswith('.csv')),
                None,
            )
            if pay_file:
                pdf = pd.read_csv(zf.open(pay_file))
                if all(c in pdf.columns for c in PAYMENT_COLUMNS):
                    save_payments(pdf[PAYMENT_COLUMNS])
                    parts.append('история оплат')
        return True, 'Восстановлено: ' + ', '.join(parts) + '.'
    except Exception as e:
        return False, str(e)


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
    border:1px solid #1e3a5f;
}
.stButton>button {
    width:100%; border-radius:10px; font-weight:600;
    background:linear-gradient(135deg,#1d4ed8,#1e40af);
    border:none; color:#fff; padding:.6rem 1rem;
}
.stat-card {
    background:rgba(14,30,54,.7); border-radius:12px; padding:14px 18px;
    border:1px solid #1e3a5f; margin-bottom:10px;
}
.bal-big {
    font-family:'Rajdhani',sans-serif; font-weight:700; font-size:2.8rem; line-height:1;
}
.badge-red { color:#f87171; }
.badge-green { color:#34d399; }
.badge-yellow { color:#fbbf24; }
.chip-green { color:#34d399; }
.chip-red { color:#f87171; }
.chip-yellow { color:#fbbf24; }
</style>
""", unsafe_allow_html=True)

df = load_data()
today = date.today()
today_dt = pd.to_datetime(today)

if not df.empty:
    df['Должник'] = df.apply(lambda r: is_debt(r, today_dt), axis=1)

with st.sidebar:
    st.markdown("## 🥋 ТРЕНЕР PRO")
    page = st.radio(
        "", ["📊 Дашборд", "📅 Посещаемость", "📋 История оплат",
             "➕ Регистрация", "⚙️ Оплата"],
        label_visibility="collapsed",
    )
    st.divider()

    st.subheader("💾 РЕЗЕРВНАЯ КОПИЯ")
    pays_sb = load_payments()
    stud_export = df.drop(columns=_TMP_COLS, errors='ignore') if not df.empty else pd.DataFrame(columns=FULL_COLUMNS)
    visits_export = visits_to_dataframe(stud_export) if not df.empty else pd.DataFrame(columns=VISIT_EXPORT_COLUMNS)

    bk1, bk2 = st.columns(2)
    with bk1:
        if not df.empty:
            st.download_button(
                "📥 Ученики",
                data=stud_export.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"students_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        if not visits_export.empty:
            st.download_button(
                "📅 Посещения",
                data=visits_export.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"visits_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        elif not df.empty:
            st.caption("Журнал посещений пуст")
    with bk2:
        if not pays_sb.empty:
            st.download_button(
                "📥 Оплаты",
                data=pays_sb.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"payments_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        if not df.empty or not pays_sb.empty:
            st.download_button(
                "📦 Полный архив",
                data=build_backup_zip(
                    df if not df.empty else pd.DataFrame(columns=FULL_COLUMNS),
                    pays_sb,
                ),
                file_name=f"coach_backup_{today}.zip",
                mime="application/zip",
                use_container_width=True,
            )

    st.caption("ZIP: ученики + оплаты + журнал посещений")

    with st.expander("📤 Восстановить из копии"):
        restore_kind = st.radio(
            "Тип файла",
            ["База учеников (CSV)", "История оплат (CSV)", "Полный архив (ZIP)"],
            label_visibility="collapsed",
        )
        up = st.file_uploader("Выберите файл", type=None, key="restore_upload")
        if up is not None:
            if restore_kind.startswith("База"):
                ok, msg = restore_students_csv(up)
            elif restore_kind.startswith("История"):
                ok, msg = restore_payments_csv(up)
            else:
                ok, msg = restore_backup_zip(up)
            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    st.divider()
    if not df.empty:
        debtors = int(df['Должник'].sum())
        st.markdown(f"**Учеников:** {len(df)}")
        if debtors:
            st.markdown(f'<span class="badge-red">🔴 Должников: {debtors}</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-green">🟢 Все оплачено</span>', unsafe_allow_html=True)

if page == "📊 Дашборд":
    st.title("Финансовый отчёт")
    if not df.empty:
        df['_active'] = df.apply(lambda r: active_value(r, today_dt), axis=1)
        df['_debt_val'] = df.apply(lambda r: debt_value(r, today_dt), axis=1)
        total_active = int(df['_active'].sum())
        total_debt = int(df['_debt_val'].sum())
        director_share = int(total_active * PERCENT_DIR)
        coach_net = total_active - director_share

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Активная база", f"{total_active:,} ₽",
                  help="Абонементы + все оплаченные разовые (включая погашённый долг)")
        c2.metric("🏢 Доля клуба 40%", f"{director_share:,} ₽")
        c3.metric("👤 Ваша чистая ЗП", f"{coach_net:,} ₽")
        c4.metric("🔴 Задолженность", f"{int(df['Должник'].sum())} чел.",
                  delta=f"⚠️ {total_debt:,} ₽" if total_debt else "Долгов нет",
                  delta_color="inverse" if total_debt else "normal")

        st.divider()
        search = st.text_input("🔍 Поиск по имени", placeholder="Введите имя...")
        view = df.drop(columns=_TMP_COLS, errors='ignore').copy()
        view['_sort_debt'] = view.apply(lambda r: 0 if is_debt(r, today_dt) else 1, axis=1)
        view['_sort_date'] = view.apply(
            lambda r: pd.to_datetime(r['Оплачено до'], errors='coerce')
            if r['Тип оплаты'] == 'Абонемент' else pd.Timestamp.min,
            axis=1,
        )
        view = view.sort_values(
            ['_sort_debt', '_sort_date', 'Имя ученика'],
            ascending=[True, True, True], na_position='first',
        ).drop(columns=['_sort_debt', '_sort_date'])

        view['Оплачено до'] = view['Оплачено до'].apply(
            lambda v: '—' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        )

        def _status(r):
            if r['Тип оплаты'] == 'Абонемент':
                val = r['Оплачено до']
                if val == '—':
                    return '❌ Не оплачен'
                dt = pd.to_datetime(val, errors='coerce')
                if pd.isna(dt) or dt < today_dt:
                    return '❌ Просрочен'
                if dt <= today_dt + pd.Timedelta(days=3):
                    return '⚠️ Истекает'
                return '✅ Активен'
            b = int(r['Баланс занятий'])
            if b > 0:
                return f'✅ {b} занятий'
            if b == 0:
                return '⚠️ Закончились'
            return f'❌ Долг {-b} зан.'

        view['Статус'] = view.apply(_status, axis=1)
        view['Посещений'] = view['Посещения'].apply(lambda v: len(parse_visits(v)))
        view['Баланс занятий'] = view.apply(
            lambda r: '—' if r['Тип оплаты'] == 'Абонемент' else str(int(r['Баланс занятий'])),
            axis=1,
        )
        view = view.rename(columns={'Сумма': 'Всего оплачено (₽)'})
        cols = ['Имя ученика', 'Тип оплаты', 'Статус', 'Оплачено до',
                'Баланс занятий', 'Всего оплачено (₽)', 'Посещений', 'Телефон', 'ФИО родителя']
        view = view[cols]
        if search.strip():
            view = view[view['Имя ученика'].astype(str).str.contains(search.strip(), case=False, na=False)]
        view.index = range(1, len(view) + 1)

        def _style(row):
            st_txt = str(row.get('Статус', ''))
            if any(x in st_txt for x in ('❌', 'Долг', 'Просрочен', 'Не оплачен')):
                return ['background:rgba(239,68,68,.12);color:#fca5a5'] * len(row)
            if st_txt == '✅ 1 занятий' or 'Истекает' in st_txt or st_txt == '⚠️ Закончились':
                return ['background:rgba(234,179,8,.1);color:#fde68a'] * len(row)
            return [''] * len(row)

        st.dataframe(view.style.apply(_style, axis=1), use_container_width=True)
        st.divider()
        student_list = sorted(df['Имя ученика'].dropna().unique().tolist())
        with st.expander("⚡ Быстрая корректировка", expanded=False):

    student_list = sorted(df['Имя ученика'].dropna().unique().tolist())

    qc_student = st.selectbox(
        "👤 Ученик",
        student_list,
        key="qc_student"
    )

    if qc_student:
        qc_idx = df[df['Имя ученика'] == qc_student].index[0]
        qc_row = df.loc[qc_idx]

        st.markdown("### ✏️ Редактирование данных")

        c1, c2 = st.columns(2)

        with c1:
            new_name = st.text_input(
                "Имя ученика",
                value=safe_str(qc_row['Имя ученика'], '')
            )

            new_birth = st.date_input(
                "Дата рождения",
                value=qc_row['Дата рождения']
                if pd.notna(qc_row['Дата рождения'])
                else today
            )

            new_parent = st.text_input(
                "ФИО родителя",
                value=safe_str(qc_row['ФИО родителя'], '')
            )

            new_phone = st.text_input(
                "Телефон",
                value=safe_str(qc_row['Телефон'], '')
            )

        with c2:

            pay_types = ["Абонемент", "Разовая"]

            current_type = qc_row['Тип оплаты']

            new_pay_type = st.selectbox(
                "Тип оплаты",
                pay_types,
                index=pay_types.index(current_type)
            )

            if new_pay_type == "Абонемент":

                new_paid = st.date_input(
                    "Оплачено до",
                    value=qc_row['Оплачено до']
                    if pd.notna(qc_row['Оплачено до'])
                    else today
                )

                new_balance = 0

            else:

                new_paid = None

                new_balance = st.number_input(
                    "Баланс занятий",
                    value=int(qc_row['Баланс занятий']),
                    step=1
                )

            new_sum = st.number_input(
                "Сумма",
                min_value=0,
                value=int(qc_row['Сумма']),
                step=100
            )

        current_visits = parse_visits(qc_row['Посещения'])

        new_visits = st.multiselect(
            "Посещения",
            options=current_visits,
            default=current_visits
        )

        if st.button("💾 Сохранить изменения", type="primary"):

            df.at[qc_idx, 'Имя ученика'] = new_name.strip()
            df.at[qc_idx, 'Дата рождения'] = new_birth
            df.at[qc_idx, 'ФИО родителя'] = new_parent.strip()
            df.at[qc_idx, 'Телефон'] = new_phone.strip()

            df.at[qc_idx, 'Тип оплаты'] = new_pay_type
            df.at[qc_idx, 'Оплачено до'] = new_paid
            df.at[qc_idx, 'Баланс занятий'] = int(new_balance)
            df.at[qc_idx, 'Сумма'] = int(new_sum)

            df.at[qc_idx, 'Посещения'] = visits_to_str(new_visits)

            save_data(df)

            log_payment(
                new_name,
                'Корректировка',
                'Быстрая правка через дашборд',
                0
            )

            st.success("✅ Данные обновлены!")
            st.rerun()
    else:
        st.info("ℹ️ База пуста. Зарегистрируйте первого ученика.")

elif page == "📅 Посещаемость":
    st.title("Журнал тренировок")
    if not df.empty:
        student_list = sorted(df['Имя ученика'].dropna().unique().tolist())
        tab_mark, tab_vis_edit = st.tabs(["📆 Отметка за день", "✏️ Корректировка посещений"])

        with tab_mark:
            target_date = st.date_input("📆 Дата тренировки", value=today, key="att_mark_date")
            tds = target_date.strftime("%Y-%m-%d")
            already = [r['Имя ученика'] for _, r in df.iterrows() if tds in parse_visits(r['Посещения'])]
            st.markdown(f"Отмечено **{len(already)}** из **{len(df)}** за {tds}")
            force_debt_mode = st.checkbox(
                "💳 Разрешить запись в долг (для разовых с балансом 0)",
                value=False, key="att_force_debt",
            )
            selected = st.multiselect(
                "✅ Присутствующие:", student_list, default=already, key="att_multiselect",
            )
            if st.button("💾 Сохранить посещаемость", type="primary", key="att_save_day"):
                blocked = []
                for idx in df.index:
                    name = df.at[idx, 'Имя ученика']
                    ptype = df.at[idx, 'Тип оплаты']
                    visits = parse_visits(df.at[idx, 'Посещения'])
                    is_sel = name in selected
                    was_here = tds in visits
                    if is_sel and not was_here:
                        if ptype == 'Разовая':
                            b = int(df.at[idx, 'Баланс занятий'])
                            if b <= 0 and not force_debt_mode:
                                blocked.append(name)
                                continue
                            df.at[idx, 'Баланс занятий'] = b - 1
                        visits.append(tds)
                    elif not is_sel and was_here:
                        visits.remove(tds)
                        if ptype == 'Разовая':
                            df.at[idx, 'Баланс занятий'] = int(df.at[idx, 'Баланс занятий']) + 1
                    df.at[idx, 'Посещения'] = visits_to_str(visits)
                save_data(df)
                if blocked:
                    st.warning(f"⛔ Не добавлены: {', '.join(blocked)}")
                st.success(f"✅ Посещаемость за {tds} сохранена!")
                st.rerun()

        with tab_vis_edit:
            st.caption("Ручное редактирование списка дат посещений ученика.")
            v_student = st.selectbox("👤 Ученик", student_list, key="vis_edit_student")
            if v_student:
                v_idx = df[df['Имя ученика'] == v_student].index[0]
                v_row = df.loc[v_idx]
                v_type = v_row['Тип оплаты']
                cur_visits = parse_visits(v_row['Посещения'])
                st.info(
                    f"Тип: **{v_type}** | сейчас посещений: **{len(cur_visits)}**"
                    + (f" | баланс: **{int(v_row['Баланс занятий'])}**" if v_type == 'Разовая' else '')
                )
                all_opts = sorted(set(cur_visits))
                edited_visits = st.multiselect(
                    "Даты посещений (снимите галочку, чтобы удалить):",
                    options=all_opts if all_opts else [today.strftime("%Y-%m-%d")],
                    default=cur_visits,
                    key=f"vis_edit_ms_{v_idx}",
                )
                extra_date = st.date_input("➕ Добавить дату", value=today, key=f"vis_edit_add_{v_idx}")
                include_extra = st.checkbox(
                    f"Добавить {extra_date.strftime('%Y-%m-%d')} при сохранении",
                    value=False, key=f"vis_edit_inc_{v_idx}",
                )
                adjust_bal = False
                if v_type == 'Разовая':
                    adjust_bal = st.checkbox(
                        "Синхронизировать баланс (−1 за новую дату, +1 за удалённую)",
                        value=True, key=f"vis_edit_adj_{v_idx}",
                    )
                if st.button("💾 Сохранить корректировку посещений", type="primary", key=f"vis_edit_save_{v_idx}"):
                    final_visits = list(edited_visits)
                    if include_extra:
                        ds = extra_date.strftime("%Y-%m-%d")
                        if ds not in final_visits:
                            final_visits.append(ds)
                    added, removed = apply_visit_correction(df, v_idx, final_visits, adjust_bal)
                    save_data(df)
                    msg = f"✅ Сохранено: {len(final_visits)} дат."
                    if v_type == 'Разовая' and adjust_bal and (added or removed):
                        msg += f" Баланс: +{removed} / −{added} занятий."
                    st.success(msg)
                    st.rerun()

        st.divider()
        month_ru = MONTHS_RU[today.month]
        st.subheader(f"📊 Статистика: {month_ru} {today.year}")
        mp = today.strftime("%Y-%m")
        stats_rows = []
        for _, r in df.iterrows():
            vs = parse_visits(r['Посещения'])
            mv = [v for v in vs if v.startswith(mp)]
            stats_rows.append({
                'Имя': r['Имя ученика'],
                'Тип': r['Тип оплаты'],
                month_ru: len(mv),
                'Всего': len(vs),
                'Баланс': int(r['Баланс занятий']) if r['Тип оплаты'] == 'Разовая' else '—',
            })
        if stats_rows:
            sdf = pd.DataFrame(stats_rows)

            def _stats_style(row):
                bal = row.get('Баланс')
                if bal == '—':
                    return [''] * len(row)
                try:
                    b = int(bal)
                except (TypeError, ValueError):
                    return [''] * len(row)
                if b < 0:
                    return ['background:rgba(239,68,68,.12);color:#fca5a5'] * len(row)
                if b == 1:
                    return ['background:rgba(234,179,8,.1);color:#fde68a'] * len(row)
                if b == 0:
                    return ['background:rgba(234,179,8,.08);color:#fde68a'] * len(row)
                return [''] * len(row)

            st.dataframe(sdf.style.apply(_stats_style, axis=1), use_container_width=True)
    else:
        st.info("ℹ️ База пуста.")

elif page == "📋 История оплат":
    st.title("История платежей")
    payments = load_payments()
    if not payments.empty:
        payments = payments.reset_index(drop=True)
        payments['Дата'] = pd.to_datetime(payments['Дата'], errors='coerce')

        tab_pay_view, tab_pay_edit = st.tabs(["📋 Журнал", "✏️ Корректировка"])

        with tab_pay_view:
            f1, f2, f3 = st.columns(3)
            with f1:
                fn = st.text_input("🔍 Ученик", placeholder="Поиск...", key="hist_fn")
            with f2:
                ft = st.selectbox(
                    "Тип", ["Все", "Абонемент", "Разовая", "Корректировка"], key="hist_ft",
                )
            with f3:
                fp = st.selectbox(
                    "Период",
                    ["Все время", "Этот месяц", "Прошлый месяц", "Последние 30 дней"],
                    key="hist_fp",
                )
            vp = payments.copy()
            if fn.strip():
                vp = vp[vp['Имя ученика'].astype(str).str.contains(fn.strip(), case=False, na=False)]
            if ft != "Все":
                vp = vp[vp['Тип'] == ft]
            if fp == "Этот месяц":
                vp = vp[(vp['Дата'].dt.year == today.year) & (vp['Дата'].dt.month == today.month)]
            elif fp == "Прошлый месяц":
                lm = today.replace(day=1) - timedelta(days=1)
                vp = vp[(vp['Дата'].dt.year == lm.year) & (vp['Дата'].dt.month == lm.month)]
            elif fp == "Последние 30 дней":
                vp = vp[vp['Дата'] >= pd.Timestamp(today - timedelta(days=30))]
            vp = vp.sort_values('Дата', ascending=False)
            m1, m2 = st.columns(2)
            m1.metric("Платежей за период", len(vp))
            m2.metric("Сумма за период", f"{int(vp['Сумма'].fillna(0).sum()):,} ₽")
            dp = vp[PAYMENT_COLUMNS].copy()
            dp['Дата'] = vp['Дата'].dt.strftime('%Y-%m-%d')
            dp.index = range(1, len(dp) + 1)
            st.dataframe(dp, use_container_width=True)

        with tab_pay_edit:
            st.caption("Изменение или удаление записи из журнала оплат.")

            def _pay_label(i: int) -> str:
                r = payments.loc[i]
                d = r['Дата']
                d_str = d.strftime('%Y-%m-%d') if pd.notna(d) else '—'
                return f"#{i + 1} | {d_str} | {r['Имя ученика']} | {r['Тип']} | {int(r['Сумма']):,} ₽"

            pay_indices = list(payments.index)
            pick_i = st.selectbox(
                "Выберите запись",
                pay_indices,
                format_func=_pay_label,
                key="hist_edit_pick",
            )
            pr = payments.loc[pick_i]
            pr_date = pr['Дата'].date() if pd.notna(pr['Дата']) else today
            ec1, ec2 = st.columns(2)
            with ec1:
                e_date = st.date_input("Дата", value=pr_date, key="hist_edit_date")
                e_student = st.text_input("Имя ученика", value=str(pr['Имя ученика']), key="hist_edit_name")
                _pay_types = ["Абонемент", "Разовая", "Корректировка"]
                _cur_type = str(pr['Тип'])
                e_type = st.selectbox(
                    "Тип",
                    _pay_types,
                    index=_pay_types.index(_cur_type) if _cur_type in _pay_types else 2,
                    key="hist_edit_type",
                )
            with ec2:
                e_desc = st.text_area("Описание", value=str(pr['Описание']), key="hist_edit_desc")
                e_sum = st.number_input(
                    "Сумма (₽)", min_value=0, value=int(pr['Сумма']), step=50, key="hist_edit_sum",
                )
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("💾 Сохранить изменения", type="primary", key="hist_edit_save"):
                    if not e_student.strip():
                        st.error("❌ Укажите имя ученика.")
                    elif update_payment_row(
                        pick_i, e_date, e_student.strip(), e_type, e_desc, int(e_sum),
                    ):
                        st.success("✅ Запись обновлена!")
                        st.rerun()
            with bc2:
                if st.button("🗑 Удалить запись", key="hist_edit_del"):
                    if delete_payment_row(pick_i):
                        st.success("✅ Запись удалена!")
                        st.rerun()
    else:
        st.info("ℹ️ История пуста.")

elif page == "➕ Регистрация":
    st.title("Новый ученик")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ФИО ученика *")
            dob = st.date_input("Дата рождения", value=date(2015, 1, 1),
                                min_value=date(1990, 1, 1), max_value=today)
            parent = st.text_input("ФИО родителя")
            phone = st.text_input("Телефон", placeholder="+7 999 000-00-00")
        with c2:
            pay_type = st.radio("Тип оплаты", ["Абонемент", "Разовая"], horizontal=True)
            if pay_type == "Абонемент":
                paid = st.date_input("Оплачено до", value=get_end_of_month(today))
                price = st.number_input("Стоимость (₽)", min_value=0, value=DEFAULT_PRICE_MONTH, step=100)
                balance = 0
            else:
                paid = None
                balance = st.number_input("Количество занятий", min_value=1, value=1, step=1)
                price = int(balance) * PRICE_PER_SESSION
        if st.form_submit_button("✅ СОХРАНИТЬ", use_container_width=True):
            name_clean = name.strip()
            if not name_clean:
                st.error("❌ Введите имя ученика!")
            elif not df.empty and name_clean.lower() in (
                df['Имя ученика'].astype(str).str.strip().str.lower().values
            ):
                st.warning(f"⚠️ Ученик «{name_clean}» уже есть!")
            else:
                new_row = pd.DataFrame([{
                    'Имя ученика': name_clean, 'Дата рождения': dob,
                    'ФИО родителя': parent.strip(), 'Телефон': phone.strip(),
                    'Тип оплаты': pay_type, 'Оплачено до': paid,
                    'Баланс занятий': int(balance), 'Сумма': int(price), 'Посещения': '',
                }])
                save_data(pd.concat(
                    [df.drop(columns=_TMP_COLS, errors='ignore'), new_row], ignore_index=True,
                ))
                if price > 0:
                    log_payment(name_clean, pay_type, "Регистрация", int(price))
                st.success(f"✅ Ученик «{name_clean}» добавлен!")
                st.rerun()

elif page == "⚙️ Оплата":
    st.title("Управление и оплата")
    if not df.empty:
        student_list = sorted(df['Имя ученика'].dropna().unique().tolist())
        student = st.selectbox("👤 Выберите ученика", student_list, key="pay_pick_student")
        if student:
            idx = df[df['Имя ученика'] == student].index[0]
            row = df.loc[idx]
            current_type = row['Тип оплаты']
            sk = str(idx)
            st.markdown(f"**{student}** — тип: **{current_type}** | всего оплачено: **{int(row['Сумма']):,} ₽**")

            tab_pay, tab_correct, tab_delete = st.tabs(["💳 Оплата", "✏️ Корректировка", "🗑 Удалить"])

            with tab_pay:
                if current_type == "Абонемент":
                    new_paid = st.date_input(
                        "Продлить до", value=get_end_of_month(today), key=f"pay_date_{sk}",
                    )
                    def_price = int(row['Сумма']) if int(row['Сумма']) > 0 else DEFAULT_PRICE_MONTH
                    new_price = st.number_input(
                        "Сумма (₽)", min_value=0, value=def_price, step=100, key=f"pay_sum_{sk}",
                    )
                    if st.button("✅ Подтвердить оплату абонемента", type="primary", key=f"pay_btn_ab_{sk}"):
                        df.at[idx, 'Оплачено до'] = new_paid
                        df.at[idx, 'Сумма'] = int(new_price)
                        save_data(df)
                        log_payment(student, 'Абонемент', f"Абонемент до {new_paid}", int(new_price))
                        st.success(f"✅ Продлён до {new_paid}!")
                        st.rerun()
                else:
                    cur_bal = int(row['Баланс занятий'])
                    cur_total = int(row['Сумма'])
                    add = st.number_input(
                        "Добавить занятий", min_value=1, value=4, step=1, key=f"pay_add_{sk}",
                    )
                    amt = int(add) * PRICE_PER_SESSION
                    st.metric("К оплате", f"{amt:,} ₽")
                    st.metric("Всего оплачено (после)", f"{cur_total + amt:,} ₽")
                    st.metric("Баланс после", f"{cur_bal + int(add)} занятий")
                    if st.button("✅ Подтвердить оплату занятий", type="primary", key=f"pay_btn_sess_{sk}"):
                        df.at[idx, 'Баланс занятий'] = cur_bal + int(add)
                        df.at[idx, 'Сумма'] = cur_total + amt
                        save_data(df)
                        log_payment(student, 'Разовая',
                                    f"Куплено {int(add)} занятий (баланс: {cur_bal + int(add)})", amt)
                        st.success(f"✅ +{int(add)} занятий. Всего оплачено: {cur_total + amt:,} ₽")
                        st.rerun()

            with tab_correct:
                if current_type == "Абонемент":
                    corr_date = st.date_input(
                        "Оплачено до", value=row['Оплачено до'] or today, key=f"corr_date_{sk}",
                    )
                    corr_price = st.number_input(
                        "Сумма (₽)", min_value=0, value=int(row['Сумма']), step=100,
                        key=f"corr_sum_{sk}",
                    )
                else:
                    corr_balance = st.number_input(
                        "Баланс занятий", value=int(row['Баланс занятий']), step=1,
                        key=f"corr_bal_{sk}",
                    )
                    corr_price = st.number_input(
                        "Всего оплачено (₽)", min_value=0, value=int(row['Сумма']), step=100,
                        key=f"corr_total_{sk}",
                    )
                if st.button("💾 Сохранить корректировку", key=f"corr_btn_{sk}"):
                    df.at[idx, 'Сумма'] = int(corr_price)
                    if current_type == "Абонемент":
                        df.at[idx, 'Оплачено до'] = corr_date
                    else:
                        df.at[idx, 'Баланс занятий'] = int(corr_balance)
                    save_data(df)
                    log_payment(student, 'Корректировка', 'Ручная правка', 0)
                    st.success("✅ Сохранено!")
                    st.rerun()

            with tab_delete:
                confirm = st.text_input("Введите имя для подтверждения:", key=f"del_confirm_{sk}")
                if st.button("🗑 Удалить", type="primary", key=f"del_btn_{sk}"):
                    if confirm.strip().lower() == student.lower():
                        save_data(df[df['Имя ученика'] != student].copy())
                        st.success("✅ Удалён.")
                        st.rerun()
                    else:
                        st.error("❌ Имя не совпадает.")
    else:
        st.info("ℹ️ База пуста.")
