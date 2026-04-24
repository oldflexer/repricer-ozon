import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import OzonParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_single_url_async():
    async with OzonParser() as parser:
        price = await parser.fetch_price_by_sku("1869466871")
        if price:
            print(f"✅ Цена товара: {price} ₽")
        else:
            print("❌ Не удалось получить цену")


if __name__ == "__main__":
    asyncio.run(test_single_url_async())