import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Ozon API
OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID')
OZON_API_KEY = os.getenv('OZON_API_KEY')
OZON_API_URL = 'https://api-seller.ozon.ru'

# MAX Bot
MAX_BOT_TOKEN = os.getenv('MAX_BOT_TOKEN')
MAX_API_URL = 'https://api.max.ru/bot/v1'

# Парсинг
PARSER_DELAY = float(os.getenv('PARSER_DELAY', '1.5'))
PARSER_TIMEOUT = int(os.getenv('PARSER_TIMEOUT', '10'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# Данные
DATA_FILE = Path(os.getenv('DATA_FILE', BASE_DIR / 'data' / 'products.xlsx'))
DATABASE_PATH = BASE_DIR / 'data' / 'repricer.db'