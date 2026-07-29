#!/usr/bin/env python3
import sys
import sqlite3
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings


def main():
    parser = argparse.ArgumentParser(description="Удалить товары без offer_id")
    parser.add_argument('--dry-run', action='store_true',
                        help="Только показать, что будет удалено")
    args = parser.parse_args()

    db_path = settings.DATABASE_PATH_PATH
    if not db_path.exists():
        print(f"Ошибка: файл БД {db_path} не найден")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    cursor = conn.cursor()

    # Находим product_id без offer_id
    cursor.execute("""
        SELECT product_id, sku, offer_id FROM product
        WHERE offer_id IS NULL OR offer_id = ''
    """)
    rows = cursor.fetchall()
    product_ids = [row['product_id'] for row in rows]

    if not product_ids:
        print("Нет товаров без offer_id. Очистка не требуется.")
        conn.close()
        return

    print(f"Найдено товаров без offer_id: {len(product_ids)}")

    if args.dry_run:
        print("Dry-run режим: удаление не будет выполнено.")
        i = 1
        for row in rows:
            print(f"  {i} product_id={row['product_id']}, sku={row['sku']}, offer_id={row['offer_id']}")
            i += 1
        conn.close()
        return

    placeholders = ','.join(['?'] * len(product_ids))

    # Удаление в правильном порядке (сначала дочерние)
    cursor.execute(f"DELETE FROM product_price_history WHERE product_id IN ({placeholders})", product_ids)
    deleted_price = cursor.rowcount
    print(f"Удалено из product_price_history: {deleted_price}")

    cursor.execute(f"DELETE FROM product_marginality_history WHERE product_id IN ({placeholders})", product_ids)
    deleted_margin = cursor.rowcount
    print(f"Удалено из product_marginality_history: {deleted_margin}")

    cursor.execute(f"DELETE FROM product_strategy WHERE product_id IN ({placeholders})", product_ids)
    deleted_strategy = cursor.rowcount
    print(f"Удалено из product_strategy: {deleted_strategy}")

    cursor.execute(f"DELETE FROM product WHERE product_id IN ({placeholders})", product_ids)
    deleted_product = cursor.rowcount
    print(f"Удалено из product: {deleted_product}")

    conn.commit()
    conn.close()
    print("Очистка завершена.")


if __name__ == "__main__":
    main()