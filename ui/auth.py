"""
Аутентификация пользователя для Streamlit-дашборда.

Проверяет логин и пароль, сравнивая с настройками WEB_USER и WEB_PASS.
При успешном входе устанавливает флаг authenticated в session_state.
"""

import streamlit as st

from config.settings import settings


def check_auth() -> None:
    """
    Проверяет аутентификацию пользователя.

    Если пользователь не аутентифицирован, показывает форму входа.
    После успешного входа перезагружает страницу.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown('<h1><i class="fa-solid fa-lock"></i> Авторизация</h1>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            if st.button("Войти", use_container_width=True, icon=":material/login:"):
                if username == settings.USER and password == settings.PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
        st.stop()
