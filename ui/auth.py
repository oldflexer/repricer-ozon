import streamlit as st
from config.settings import settings


def check_auth() -> None:
    """Проверка аутентификации пользователя."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Авторизация")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            if st.button("Войти", use_container_width=True):
                if username == settings.WEB_USER and password == settings.WEB_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
        st.stop()