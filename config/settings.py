# config/settings.py
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

# Расчёт цен
COEFFICIENT_OZON = float(os.getenv('COEFFICIENT_OZON', '0.5'))

HEADLESS_RAW = os.getenv('HEADLESS', 'True').strip().lower()
if HEADLESS_RAW in ('true', '1'):
    HEADLESS = True
elif HEADLESS_RAW in ('false', '0'):
    HEADLESS = False
else:
    HEADLESS = True  # fallback

# Данные
DATA_FILE = Path(os.getenv('DATA_FILE', BASE_DIR / 'data' / 'products.xlsx'))
DATABASE_PATH = BASE_DIR / 'data' / 'repricer.db'