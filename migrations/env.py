"""
Окружение для Alembic миграций.

Настраивает подключение к SQLite, подставляя путь к БД из настроек
(с учётом INSTANCE_NAME). Поддерживает offline и online режимы.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Добавляем корень проекта в sys.path для импорта настроек
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings

# Объект конфигурации Alembic (из alembic.ini)
config = context.config

# Настройка логирования из конфигурационного файла (если указан)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Подстановка пути к БД из настроек (с поддержкой INSTANCE_NAME)
db_path = settings.DATABASE_PATH_PATH.resolve()
db_uri = f"sqlite:///{db_path.as_posix()}"
config.set_main_option("sqlalchemy.url", db_uri)

# Метаданные моделей (у нас нет ORM, поэтому None)
target_metadata = None


def run_migrations_offline() -> None:
    """
    Запуск миграций в 'offline' режиме.

    Используется для генерации SQL-скриптов без подключения к БД.
    """
    context.configure(
        url=db_uri,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Запуск миграций в 'online' режиме.

    Устанавливает соединение с БД и выполняет миграции.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# Определение режима выполнения
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()