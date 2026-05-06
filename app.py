# --- СТРАНИЦА: РЕГИСТРАЦИЯ ---
elif page == "➕ Регистрация":
    st.title("Новая карточка")
    with st.container():
        with st.form("add_student"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("ФИО ученика*")
                dob = st.date_input("Дата рождения", value=date(2015, 1, 1))
            with c2:
                parent = st.text_input("Родитель")
                phone = st.text_input("Телефон")
            
            paid_until = st.date_input("Оплачено до", value=get_end_of_month(date.today()))
            
            submit_button = st.form_submit_button("Добавить в систему", use_container_width=True)
            
            if submit_button:
                clean_name = name.strip()
                
                # 1. Проверка на пустое поле
                if not clean_name:
                    st.error("Поле 'Имя ученика' обязательно!")
                
                # 2. ПРОВЕРКА НА ПОВТОР (без учета регистра)
                elif clean_name.lower() in df['Имя ученика'].str.lower().values:
                    st.warning(f"Ученик с именем '{clean_name}' уже есть в базе. Повторное добавление невозможно.")
                
                # 3. Если всё в порядке — сохраняем
                else:
                    new_student = pd.DataFrame([{
                        'Имя ученика': clean_name,
                        'Дата рождения': dob,
                        'ФИО родителя': parent.strip(),
                        'Телефон': phone.strip(),
                        'Оплачено до': paid_until
                    }])
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success(f"Ученик {clean_name} успешно добавлен!")
                    st.rerun()
