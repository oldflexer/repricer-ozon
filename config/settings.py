import os
from pathlib import Path
from dotenv import load_dotenv
import pytz

TIMEZONE = pytz.timezone('Europe/Moscow')

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Ozon API
OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID')
OZON_API_KEY = os.getenv('OZON_API_KEY')
OZON_API_URL = 'https://api-seller.ozon.ru'
# Email
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.yandex.ru')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', SMTP_USER)
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# Парсинг
PARSER_DELAY = float(os.getenv('PARSER_DELAY', '1.5'))
PARSER_TIMEOUT = int(os.getenv('PARSER_TIMEOUT', '10'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# Headless
HEADLESS = os.getenv('HEADLESS', 'false').lower() == 'true'

# Данные
DATA_FILE = Path(os.getenv('DATA_FILE', BASE_DIR / 'data' / 'products.xlsx'))
DATABASE_PATH = BASE_DIR / 'data' / 'repricer.db'