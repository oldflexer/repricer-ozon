import asyncio
import logging
from src.parser import OzonParser, SyncOzonParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Асинхронный тест (рекомендуемый)
async def test_single_url_async():
    url = "https://www.ozon.ru/product/pritochnyy-klapan-ventilyatsionnyy-v-stenu-airglass-kiv-125-ogolovok-kiv-125-diffuzor-anemostat-1869466871"

    async with OzonParser() as parser:
        price = await parser.fetch_price(url)
        if price:
            print(f"✅ Цена товара: {price} ₽")
        else:
            print("❌ Не удалось получить цену")

# Синхронный тест (через обёртку)
def test_single_url_sync():
    url = "https://www.ozon.ru/product/pritochnyy-klapan-ventilyatsionnyy-v-stenu-airglass-kiv-125-ogolovok-kiv-125-diffuzor-anemostat-1869466871"

    with SyncOzonParser() as parser:
        price = parser.fetch_price(url)
        if price:
            print(f"✅ Цена товара: {price} ₽")
        else:
            print("❌ Не удалось получить цену")

if __name__ == "__main__":
    # Выберите нужный вариант
    asyncio.run(test_single_url_async())
    # test_single_url_sync()