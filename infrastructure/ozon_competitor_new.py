"""
New parser for Ozon competitor prices using httpx + selectolax.

Replaces fragile Selenium-based parser with fast, lightweight HTTP scraping.
"""

import asyncio
import random
import re
import time
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from config.settings import settings
from core.protocols.parser import OzonPriceParserBase
from infrastructure.logger import logger


class OzonPriceParserNew(OzonPriceParserBase):
    """
    New parser for Ozon competitor prices using httpx + selectolax.

    Fast, lightweight, no browser dependency. Uses async HTTP client
    with connection pooling for high performance.
    """

    def __init__(
        self,
        headless: bool = True,  # ignored, kept for interface compatibility
        timeout: float = 30.0,
        max_retries: int = 3,
        request_delay_min: float = 2.0,
        request_delay_max: float = 5.0,
    ) -> None:
        """
        Initialize the new parser.

        Args:
            headless: Ignored (kept for interface compatibility).
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            request_delay_min: Minimum delay between requests (seconds).
            request_delay_max: Maximum delay between requests (seconds).
        """
        self._timeout = timeout
        self._max_retries = max_retries
        self._request_delay_min = request_delay_min
        self._request_delay_max = request_delay_max

        # HTTP client with connection pooling
        self._client: httpx.AsyncClient | None = None
        self._last_request_time = 0.0

        # Price selectors (same as old parser for compatibility)
        self._price_selectors = [
            'span[data-testid="price-price"]',
            "span.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline500Medium",
            'div[data-testid="price"] span',
            'span[class*="tsHeadline"]',
        ]

        # Default headers to mimic real browser
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                headers=self._headers,
                follow_redirects=True,
            )
        return self._client

    async def _respect_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        min_delay = random.uniform(self._request_delay_min, self._request_delay_max)
        if elapsed < min_delay:
            await asyncio.sleep(min_delay - elapsed)
        self._last_request_time = time.time()

    async def get_price(self, product_url: str) -> Optional[float]:
        """
        Get competitor price from Ozon product page.

        Args:
            product_url: Full URL to the Ozon product page.

        Returns:
            Price as float, -1.0 if product is out of stock,
            or None if price could not be determined.
        """
        if not product_url or not product_url.startswith("http"):
            logger.warning(f"Invalid URL: {product_url}")
            return None

        await self._respect_rate_limit()

        client = await self._get_client()

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(f"Fetching price (attempt {attempt}/{self._max_retries}): {product_url}")

                response = await client.get(product_url)
                response.raise_for_status()

                html = response.text

                # Check for anti-bot / CAPTCHA
                if "captcha" in response.text.lower() or "access denied" in response.text.lower():
                    logger.warning(f"Possible CAPTCHA/anti-bot detected for {product_url}")
                    if attempt < self._max_retries:
                        await asyncio.sleep(random.uniform(5, 10))
                        continue
                    return None

                price = self._parse_price(html)

                if price is not None:
                    logger.info(f"Price found: {price} for {product_url}")
                    return price

                logger.warning(f"Price not found (attempt {attempt}/{self._max_retries}): {product_url}")

            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {product_url} (attempt {attempt})")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {product_url} (attempt {attempt})")
                if e.response.status_code == 404:
                    return None  # Product not found, don't retry
                if e.response.status_code >= 500:
                    # Server error, retry
                    pass
                else:
                    return None  # Client error, don't retry
            except Exception as e:
                logger.error(f"Error fetching {product_url} (attempt {attempt}): {e}")

            if attempt < self._max_retries:
                # Exponential backoff with jitter
                delay = min(2 ** attempt + random.uniform(0, 1), 30)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        logger.error(f"All attempts failed for {product_url}")
        return None

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            # Use asyncio to close properly
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule close for later
                    loop.create_task(self._client.aclose())
                else:
                    loop.run_until_complete(self._client.aclose())
            except RuntimeError:
                # No event loop, create one
                asyncio.run(self._client.aclose())
            self._client = None
        logger.info("Parser closed")

    def restart(self) -> None:
        """Restart the parser by closing and recreating the client."""
        self.close()
        # Client will be recreated on next request
        logger.info("Parser restarted")

    def _parse_price(self, html: str) -> Optional[float]:
        """
        Parse price from HTML content.

        Args:
            html: Raw HTML content of the product page.

        Returns:
            Parsed price as float, or None if not found.
        """
        tree = HTMLParser(html)

        # Check for out of stock
        out_of_stock = tree.css_first("h2:contains('Этот товар закончился')")
        if out_of_stock:
            logger.info("Product out of stock (found in HTML)")
            return -1.0

        # Try each price selector
        for selector in self._price_selectors:
            try:
                elements = tree.css(selector)
                for el in elements:
                    text = el.text(strip=True)
                    if "₽" in text or "руб" in text.lower():
                        price = self._clean_price(text)
                        if price is not None and price > 0:
                            return price
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue

        logger.warning("Price not found with any selector")
        return None

    def _clean_price(self, raw_price: str) -> Optional[float]:
        """
        Clean and parse price string.

        Args:
            raw_price: Raw price text (e.g., "1 234 ₽", "1,234.56 ₽").

        Returns:
            Parsed price as float, or None if parsing failed.
        """
        try:
            # Remove currency symbols and non-numeric chars except digits, dot, comma
            cleaned = re.sub(r"[^\d.,]", "", raw_price)
            # Replace comma with dot for decimal
            cleaned = cleaned.replace(",", ".")
            # Handle thousands separators (dots)
            parts = cleaned.split(".")
            if len(parts) > 2:
                # Multiple dots - assume all but last are thousands separators
                cleaned = "".join(parts[:-1]) + "." + parts[-1]
            price = float(cleaned)
            return price if price > 0 else None
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse price '{raw_price}': {e}")
            return None
