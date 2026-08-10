"""
Страница «Таблицы» дашборда.

Отображает содержимое всех таблиц SQLite-БД в виде вкладок.
"""

import pandas as pd
import streamlit as st

from ui.cache import get_repo


def render_tables() -> None:
    """
    Рендерит страницу с просмотром таблиц БД.
    """
    st.markdown(
        '<h2><i class="fa-solid fa-table"></i> Таблицы БД</h2>',
        unsafe_allow_html=True,
    )
    repo = get_repo()

    with repo._get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]

    if not table_names:
        st.info("Нет таблиц в базе данных")
        return

    tabs = st.tabs(table_names)
    for tab, table_name in zip(tabs, table_names, strict=False):
        with tab:
            with repo._get_connection() as conn:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            if not df.empty:
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info(f"Таблица '{table_name}' пуста")
