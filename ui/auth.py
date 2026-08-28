"""
Аутентификация пользователя для Streamlit-дашборда.

Проверяет логин и пароль, используя bcrypt для хеширования паролей.
Поддерживает миграцию с plain text пароля на bcrypt hash.
Управляет сессиями с таймаутом.
"""

import hashlib
import secrets
import time
from typing import Any, Optional

import bcrypt  # type: ignore[import-not-found]
import streamlit as st

from config.settings import settings
from config.ui import UiSettings

# Get ui_settings instance from the global settings
from config.settings import settings as global_settings
ui_settings = global_settings


# Session state keys
SESSION_AUTH_KEY = "repricer_authenticated"
SESSION_USER_KEY = "repricer_user"
SESSION_EXPIRY_KEY = "repricer_session_expiry"
SESSION_TOKEN_KEY = "repricer_session_token"


def hash_password(plain: str) -> str:
    """Хеширует пароль с использованием bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode(), salt).decode()  # type: ignore[no-any-return]


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет пароль против bcrypt хеша."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())  # type: ignore[no-any-return]
    except Exception:
        return False


def migrate_password_if_needed() -> Optional[str]:
    """
    Мигрирует plain text пароль в bcrypt hash при первом запуске.
    Возвращает хеш если миграция произошла, иначе None.
    """
    if ui_settings.WEB_PASS and not ui_settings.WEB_PASS_HASH:
        # Хешируем пароль и сохраняем в session_state для текущего запуска
        # В продакшене нужно обновить .env файл с WEB_PASS_HASH
        hashed = hash_password(ui_settings.WEB_PASS)
        st.session_state["migrated_password_hash"] = hashed
        return hashed
    return None


def check_password(username: str, password: str) -> bool:
    """Проверяет логин и пароль."""
    if username != settings.WEB_USER:
        return False
    
    # Сначала проверяем мигрированный хеш
    if "migrated_password_hash" in st.session_state:
        return verify_password(password, st.session_state["migrated_password_hash"])
    
    # Проверяем настроенный хеш
    if ui_settings.WEB_PASS_HASH:
        return verify_password(password, ui_settings.WEB_PASS_HASH)
    
    # Fallback на plain text (для обратной совместимости)
    if ui_settings.WEB_PASS:
        return password == ui_settings.WEB_PASS  # type: ignore[no-any-return]
    
    return False


def create_session(username: str) -> str:
    """Создает новую сессию и возвращает токен."""
    token = secrets.token_urlsafe(32)
    expiry = time.time() + ui_settings.SESSION_TIMEOUT_MINUTES * 60
    
    st.session_state[SESSION_AUTH_KEY] = True
    st.session_state[SESSION_USER_KEY] = username
    st.session_state[SESSION_TOKEN_KEY] = token
    st.session_state[SESSION_EXPIRY_KEY] = expiry
    
    return token


def validate_session() -> bool:
    """Проверяет валидность текущей сессии."""
    if not st.session_state.get(SESSION_AUTH_KEY, False):
        return False
    
    token = st.session_state.get(SESSION_TOKEN_KEY)
    if not token:
        return False
    
    expiry = st.session_state.get(SESSION_EXPIRY_KEY, 0)
    if time.time() > expiry:
        clear_session()
        return False
    
    # Продлеваем сессию при активности
    st.session_state[SESSION_EXPIRY_KEY] = time.time() + ui_settings.SESSION_TIMEOUT_MINUTES * 60
    return True


def clear_session() -> None:
    """Очищает данные сессии."""
    for key in [SESSION_AUTH_KEY, SESSION_USER_KEY, SESSION_TOKEN_KEY, SESSION_EXPIRY_KEY]:
        st.session_state.pop(key, None)


def get_session_info() -> dict:
    """Возвращает информацию о текущей сессии."""
    if not validate_session():
        return {"authenticated": False}
    
    expiry = st.session_state.get(SESSION_EXPIRY_KEY, 0)
    remaining = max(0, int(expiry - time.time()))
    
    return {
        "authenticated": True,
        "user": st.session_state.get(SESSION_USER_KEY, ""),
        "token": st.session_state.get(SESSION_TOKEN_KEY, "")[:8] + "...",
        "expires_in_seconds": remaining,
    }


def require_auth() -> bool:
    """
    Требует аутентификацию - показывает форму входа если не аутентифицирован.
    Возвращает True если аутентифицирован, False если показана форма входа.
    """
    # Сначала пробуем мигрировать пароль
    migrate_password_if_needed()
    
    if validate_session():
        return True
    
    # Показываем форму входа
    st.markdown('<h1><i class="fa-solid fa-lock"></i> Авторизация</h1>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        if st.button("Войти", use_container_width=True, icon=":material/login:"):
            if check_password(username, password):
                create_session(username)
                st.success("Успешный вход!")
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    st.stop()
    return False


def logout() -> None:
    """Выход из системы."""
    clear_session()
    st.success("Вы вышли из системы")
    st.rerun()


def check_auth() -> None:
    """
    Проверяет аутентификацию пользователя (обратная совместимость).
    Использует новую систему сессий.
    """
    require_auth()
