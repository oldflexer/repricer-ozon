import streamlit as st
import plotly.express as px
from ui.cache import get_repo


def render_service():
    st.header("🛠️ Сервисные инструменты")
    repo = get_repo()

    st.subheader("Тепловая карта обновлений")
    heatmap_data = repo.get_update_heatmap(days=90)
    if not heatmap_data.empty:
        weekday_map = {0: 'Вс', 1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб'}
        heatmap_data['weekday_label'] = heatmap_data['weekday'].astype(int).map(weekday_map)
        pivot = heatmap_data.pivot(index='hour', columns='weekday_label', values='updates').fillna(0)
        correct_order = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        pivot = pivot.reindex(columns=correct_order, fill_value=0)
        fig_heatmap = px.imshow(pivot,
                                labels=dict(x="День недели", y="Час (МСК)", color="Количество обновлений"),
                                title="Тепловая карта обновлений цен (90 дней)",
                                aspect="auto", color_continuous_scale="Viridis")
        st.plotly_chart(fig_heatmap, width="stretch")
    else:
        st.info("Недостаточно данных для тепловой карты")

    # Здесь можно добавить другие диагностические инструменты
    st.divider()
    st.subheader("Диагностика")
    if st.button("Проверить соединение с БД"):
        try:
            repo.get_last_run_time()
            st.success("✅ База данных доступна")
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")