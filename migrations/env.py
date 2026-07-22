# migrations/env.py

import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Добавляем корень проекта в sys.path для импорта settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Интерпретируем файл конфигурации для логирования.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Подставляем путь к БД из настроек (поддержка INSTANCE_NAME)
db_path = settings.DATABASE_PATH_PATH.resolve()
db_uri = f"sqlite:///{db_path.as_posix()}"
config.set_main_option("sqlalchemy.url", db_uri)

# Добавляем метаданные моделей (у нас нет ORM, оставляем пустым)
target_metadata = None

def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме."""
    context.configure(
        url=db_uri,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме."""
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()