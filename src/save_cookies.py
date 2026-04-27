import asyncio
import json
import zendriver as zd

async def save_cookies():
    browser = await zd.start(headless=False)  # видимый браузер
    tab = await browser.get("https://www.ozon.ru")
    
    print("Откройте Ozon, при необходимости пройдите капчу, просто полазайте по сайту 30 секунд.")
    await asyncio.sleep(30)  # время на ручные действия
    
    cookies = await browser.cookies.get_all()
    with open("ozon_cookies.json", "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, default=str)
    
    print(f"Сохранено {len(cookies)} куки в ozon_cookies.json")
    await browser.stop()

asyncio.run(save_cookies())