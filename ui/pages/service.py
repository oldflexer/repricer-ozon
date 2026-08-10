"""
Страница «Сервис» дашборда.

Содержит сервисные инструменты:
    - тепловая карта обновлений,
    - информация о последнем запуске,
    - работа с БД (скачивание, очистка),
    - информация о файлах,
    - смена пароля,
    - диагностика БД.
"""

from pathlib import Path

import plotly.express as px
import streamlit as st

from config.settings import TIMEZONE, settings
from ui.cache import get_repo


def render_service() -> None:
    """
    Рендерит страницу «Сервис» с сервисными инструментами.
    """
    st.markdown(
        '<h2><i class="fa-solid fa-screwdriver-wrench"></i> Сервисные инструменты</h2>',
        unsafe_allow_html=True,
    )
    repo = get_repo()

    # Тепловая карта
    st.subheader("Тепловая карта обновлений")
    heatmap_data = repo.get_update_heatmap(days=90)
    if not heatmap_data.empty:
        weekday_map = {0: "Вс", 1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб"}
        heatmap_data["weekday_label"] = heatmap_data["weekday"].astype(int).map(weekday_map)
        pivot = heatmap_data.pivot(
            index="hour",
            columns="weekday_label",
            values="updates",
        ).fillna(0)
        correct_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        pivot = pivot.reindex(columns=correct_order, fill_value=0)
        fig_heatmap = px.imshow(
            pivot,
            labels=dict(x="День недели", y="Час (МСК)", color="Количество обновлений"),
            title="Тепловая карта обновлений цен (90 дней)",
            aspect="auto",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig_heatmap, width="stretch")
    else:
        st.info("Недостаточно данных для тепловой карты", icon=":material/info:")

    st.divider()

    # Последний запуск
    st.subheader("Последний запуск")
    last_run_utc = repo.get_last_run_time()
    if last_run_utc:
        last_run_msk = last_run_utc.astimezone(TIMEZONE)
        st.markdown(
            f'<i class="fa-regular fa-clock"></i> Последний запуск (МСК): '
            f'{last_run_msk.strftime("%Y-%m-%d %H:%M")}',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<i class="fa-regular fa-clock"></i> Последний запуск: —',
            unsafe_allow_html=True,
        )

    # Работа с БД
    st.divider()
    st.subheader("Работа с БД")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Скачать БД", icon=":material/save:"):
            db_data = (
                open(settings.DATABASE_PATH_PATH, "rb").read()
                if settings.DATABASE_PATH_PATH.exists()
                else b""
            )
            st.download_button(
                "Скачать",
                data=db_data,
                file_name=settings.DATABASE_PATH_PATH.name,
                mime="application/octet-stream",
            )
    with col2:
        if st.button("Удалить записи старше 1 месяца", icon=":material/cleaning_services:"):
            try:
                deleted = repo.delete_old_records(days=30)
                st.success(f"Удалено записей: {deleted}", icon=":material/check_circle:")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Ошибка при удалении: {e}", icon=":material/cancel:")

    last_cleanup = repo.get_last_cleanup_date()
    if last_cleanup:
        last_cleanup_msk = last_cleanup.astimezone(TIMEZONE)
        st.caption(f"Последняя очистка БД: {last_cleanup_msk.strftime('%Y-%m-%d %H:%M')}")

    # Информация о файлах
    st.divider()
    st.subheader("Информация о файлах")
    st.caption(f"Файл данных: {settings.DATA_FILE_PATH.resolve()}")
    st.caption(f"База данных: {settings.DATABASE_PATH_PATH.resolve()}")

    # Изменение пароля
    st.divider()
    with st.expander("Изменить пароль", icon=":material/lock:"):
        new_password = st.text_input("Новый пароль", type="password", key="new_pass")
        confirm_password = st.text_input("Подтвердите пароль", type="password", key="confirm_pass")
        if st.button("Сохранить пароль", use_container_width=True, icon=":material/save:"):
            if new_password and new_password == confirm_password:
                env_path = Path(__file__).parent.parent.parent / ".env"
                if env_path.exists():
                    with open(env_path, encoding="utf-8") as f:
                        lines = f.readlines()
                    with open(env_path, "w", encoding="utf-8") as f:
                        for line in lines:
                            if line.startswith("WEB_PASS="):
                                f.write(f"WEB_PASS={new_password}\n")
                            else:
                                f.write(line)
                    st.success(
                        "Пароль изменён. При следующем входе используйте новый пароль.",
                        icon=":material/check_circle:",
                    )
                else:
                    st.error("Файл .env не найден", icon=":material/cancel:")
            else:
                st.error("Пароли не совпадают или пусты", icon=":material/cancel:")

    # Диагностика
    st.divider()
    st.subheader("Диагностика")
    if st.button("Проверить соединение с БД", icon=":material/database:"):
        try:
            repo.get_last_run_time()
            st.success("База данных доступна", icon=":material/check_circle:")
        except Exception as e:
            st.error(f"Ошибка: {e}", icon=":material/cancel:")
