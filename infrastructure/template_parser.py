"""
Парсер шаблона цен Ozon.
Извлекает данные из листа "Товары и цены", рассчитывает реальную цену.
"""

import pandas as pd
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from infrastructure.logger import logger


class TemplateParser:
    """
    Класс для парсинга и расчёта реальной цены из шаблона Ozon.
    """

    COLUMN_NAMES = {
        "sku": "SKU",
        "status": "Статус",
        "visibility": "Видимость на OZON",
        "stock_ozon": "На складе Ozon",
        "stock_my": "На моих складах",
        "price_before_discount": "Цена до скидки, руб.",
        "price_with_discount": "Цена с учетом акции или стратегии, руб.",
        "discount_with_action": "Скидка с учетом акции, руб.",
        "acquiring": "Эквайринг",
        "fbo_reward_percent": "Вознаграждение Ozon, FBO, %",
        "fbo_logistics_min": "Логистика Ozon, минимум, FBO",
        "fbo_logistics_max": "Логистика Ozon, максимум, FBO",
        "fbo_delivery": "Доставка до места выдачи, FBO",
        "fbo_handling": "Обработка нестандартного товара, FBO",
        "fbs_reward_percent": "Вознаграждение Ozon, FBS, %",
        "fbs_handling_min": "Обработка отправления, минимум FBS",
        "fbs_handling_max": "Обработка отправления, максимум FBS",
        "fbs_handling_nonstandard": "Обработка нестандартного товара, FBS",
        "fbs_logistics_min": "Логистика Ozon, минимум, FBS",
        "fbs_logistics_max": "Логистика Ozon, максимум, FBS",
        "fbs_delivery": "Доставка до места выдачи, FBS",
    }

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.df = None

    def _read_xlsx_via_zip(self) -> Optional[pd.DataFrame]:
        """
        Читает xlsx как zip-архив, извлекая данные напрямую из XML,
        минуя повреждённые стили.
        """
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                # Получаем список файлов листов
                sheet_files = [f for f in zf.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')]
                sheet_files.sort()
                logger.info(f"Найдены листы: {sheet_files}")

                # Ищем лист с заголовками SKU и Статус
                target_sheet = None
                for sf in sheet_files:
                    try:
                        content = zf.read(sf).decode('utf-8', errors='ignore')
                        if 'SKU' in content and 'Статус' in content:
                            target_sheet = sf
                            logger.info(f"Найден лист с данными: {sf}")
                            break
                    except:
                        continue

                if not target_sheet:
                    # Если не нашли, берём второй лист (индекс 1)
                    if len(sheet_files) >= 2:
                        target_sheet = sheet_files[1]
                        logger.info(f"Используем второй лист: {target_sheet}")
                    else:
                        logger.error("Не найден лист с данными")
                        return None

                # Читаем shared strings
                shared_strings = []
                try:
                    ss_xml = zf.read('xl/sharedStrings.xml')
                    ss_root = ET.fromstring(ss_xml)
                    for si in ss_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                        texts = [t.text or '' for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')]
                        shared_strings.append(''.join(texts))
                    logger.info(f"Загружено {len(shared_strings)} общих строк")
                except Exception as e:
                    logger.warning(f"Не удалось прочитать sharedStrings: {e}")

                # Читаем сам лист
                sheet_xml = zf.read(target_sheet)
                root = ET.fromstring(sheet_xml)
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

                rows = []
                for row_elem in root.findall('.//main:row', ns):
                    row_data = []
                    for cell in row_elem.findall('.//main:c', ns):
                        cell_type = cell.get('t')
                        value_elem = cell.find('.//main:v', ns)
                        if value_elem is not None:
                            value = value_elem.text
                            if cell_type == 's' and value is not None:
                                idx = int(value)
                                if idx < len(shared_strings):
                                    value = shared_strings[idx]
                                else:
                                    value = ''
                        else:
                            value = ''
                        row_data.append(value)
                    if any(row_data):  # пропускаем пустые строки
                        rows.append(row_data)

                if len(rows) < 2:
                    logger.error("Недостаточно данных в листе")
                    return None

                headers = rows[1]  # вторая строка
                # Удаляем пустые заголовки справа
                while headers and not headers[-1]:
                    headers.pop()

                data = rows[2:]  # данные начиная с третьей строки
                data = [row[:len(headers)] for row in data]  # обрезаем до длины заголовков

                df = pd.DataFrame(data, columns=headers)
                logger.info(f"Из zip-архива получено {len(df)} строк")
                return df

        except Exception as e:
            logger.error(f"Ошибка при чтении через zip: {e}")
            return None

    def load(self) -> bool:
        """
        Загружает Excel-файл, сначала через openpyxl, при ошибке через zip.
        """
        # Попытка через openpyxl
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.file_path, data_only=True, read_only=True, keep_links=False)
            if "Товары и цены" not in wb.sheetnames:
                logger.error("Лист 'Товары и цены' не найден")
                wb.close()
                return False
            ws = wb["Товары и цены"]
            data = []
            headers = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    continue  # первая строка служебная
                elif i == 1:
                    headers = [str(cell).strip() if cell is not None else '' for cell in row]
                    while headers and not headers[-1]:
                        headers.pop()
                    continue
                else:
                    if any(cell is not None for cell in row):
                        data.append(row[:len(headers)])
            wb.close()
            self.df = pd.DataFrame(data, columns=headers)
            logger.info(f"Загружен через openpyxl, строк: {len(self.df)}")
        except Exception as e:
            logger.error(f"Ошибка openpyxl: {e}")
            logger.info("Пробуем прямой разбор zip-архива...")
            self.df = self._read_xlsx_via_zip()
            if self.df is None:
                logger.error("Не удалось прочитать файл")
                return False
            logger.info(f"Загружен через zip, строк: {len(self.df)}")

        # Проверка наличия всех необходимых столбцов
        missing = []
        for key, col_name in self.COLUMN_NAMES.items():
            if col_name not in self.df.columns:
                missing.append(col_name)
        if missing:
            logger.error(f"Не найдены столбцы: {missing}")
            return False

        # Преобразование числовых столбцов
        numeric_cols = [
            "stock_ozon", "stock_my",
            "price_before_discount", "price_with_discount", "discount_with_action",
            "acquiring", "fbo_reward_percent", "fbo_logistics_min", "fbo_logistics_max",
            "fbo_delivery", "fbo_handling", "fbs_reward_percent",
            "fbs_handling_min", "fbs_handling_max", "fbs_handling_nonstandard",
            "fbs_logistics_min", "fbs_logistics_max", "fbs_delivery"
        ]
        for col in numeric_cols:
            if col in self.COLUMN_NAMES:
                col_name = self.COLUMN_NAMES[col]
                self.df[col_name] = pd.to_numeric(self.df[col_name], errors='coerce')

        logger.info("✅ Файл успешно загружен и подготовлен")
        return True

    def get_relevant_products(self) -> List[Dict]:
        if self.df is None:
            logger.error("Данные не загружены")
            return []

        status_col = self.COLUMN_NAMES["status"]
        visibility_col = self.COLUMN_NAMES["visibility"]

        mask = (self.df[status_col] == "Продается") & \
               (self.df[visibility_col].str.lower() == "да")
        filtered = self.df[mask].copy()

        if filtered.empty:
            logger.warning("Нет товаров, соответствующих критериям")
            return []

        products = []
        for _, row in filtered.iterrows():
            product = {}
            for key, col_name in self.COLUMN_NAMES.items():
                product[key] = row[col_name]
            products.append(product)

        logger.info(f"Найдено {len(products)} товаров для расчёта")
        return products

    def determine_sales_type(self, product: Dict) -> str:
        stock_ozon = product.get("stock_ozon", 0)
        stock_my = product.get("stock_my", 0)

        if pd.isna(stock_ozon):
            stock_ozon = 0
        if pd.isna(stock_my):
            stock_my = 0

        if stock_ozon > 0 and stock_my > 0:
            return "mixed"
        elif stock_ozon > 0:
            return "fbo"
        elif stock_my > 0:
            return "fbs"
        else:
            return "none"

    def calculate_real_price(self, product: Dict) -> Optional[float]:
        sales_type = self.determine_sales_type(product)
        if sales_type == "none":
            return None

        price_before = product.get("price_before_discount", 0)
        discount_with_action = product.get("discount_with_action", 0)
        base_price = price_before - discount_with_action

        if sales_type in ("fbo", "fbs"):
            return base_price

        if sales_type == "mixed":
            price_with_discount = product.get("price_with_discount", 0)
            acquiring = product.get("acquiring", 0)
            fbo_reward = product.get("fbo_reward_percent", 0) / 100
            fbo_log_min = product.get("fbo_logistics_min", 0)
            fbo_log_max = product.get("fbo_logistics_max", 0)
            fbo_delivery = product.get("fbo_delivery", 0)
            fbo_handling = product.get("fbo_handling", 0)

            fbs_reward = product.get("fbs_reward_percent", 0) / 100
            fbs_hand_min = product.get("fbs_handling_min", 0)
            fbs_hand_max = product.get("fbs_handling_max", 0)
            fbs_hand_nonstd = product.get("fbs_handling_nonstandard", 0)
            fbs_log_min = product.get("fbs_logistics_min", 0)
            fbs_log_max = product.get("fbs_logistics_max", 0)
            fbs_delivery = product.get("fbs_delivery", 0)

            numerator = (
                acquiring +
                (fbo_reward * price_with_discount) +
                ((fbo_log_min + fbo_log_max) / 2) +
                fbo_delivery +
                fbo_handling
            )
            denominator = (
                (fbs_reward * price_with_discount) +
                ((fbs_hand_min + fbs_hand_max) / 2) +
                fbs_hand_nonstd +
                ((fbs_log_min + fbs_log_max) / 2) +
                fbs_delivery
            )

            if denominator == 0:
                logger.warning(f"Нулевой знаменатель для SKU {product.get('sku')}")
                return None

            real_price = base_price * (numerator / denominator)
            return round(real_price)
        return None

    def process(self) -> List[Tuple[Dict, Optional[float], str]]:
        products = self.get_relevant_products()
        results = []
        for p in products:
            sales_type = self.determine_sales_type(p)
            if sales_type == "none":
                continue
            real_price = self.calculate_real_price(p)
            results.append((p, real_price, sales_type))
        return results