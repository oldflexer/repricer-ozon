# Parser Replacement Evaluation Document

## Executive Summary

This document evaluates alternatives to replace the fragile Selenium-based parser (`OzonPriceParser`) with a more robust solution for fetching competitor prices from Ozon.

## Current State Analysis

### Current Implementation: `OzonPriceParser` (Selenium-based)

**Location:** `infrastructure/ozon_competitor.py`

**Dependencies:**
- `selenium==4.46.0`
- `undetected-chromedriver==3.5.5`
- `webdriver-manager==4.1.2`
- Chrome browser with user profile

**How it works:**
1. Launches Chrome browser with user profile (for authentication)
2. Navigates to competitor product URL
3. Waits for page load (5-10 seconds random delay)
4. Checks if product is out of stock
5. Searches for price element using multiple CSS selectors
6. Extracts and parses price text

**Pain Points:**
- **Fragile**: Breaks on HTML/CSS changes (selectors need constant updates)
- **Slow**: 5-10 seconds per request + browser startup time
- **Resource intensive**: Requires full Chrome browser
- **Unreliable**: Flaky due to timing issues, CAPTCHA, anti-bot measures
- **Maintenance burden**: ChromeDriver version management, profile corruption
- **No headless stability**: Headless mode often detected and blocked
- **Single-threaded**: Cannot parallelize easily

## Alternatives Evaluation

### Option 1: Ozon Official API (Competitor Prices)

| Aspect | Assessment |
|--------|------------|
| **Availability** | ❌ **Not available** - Ozon Seller API does not expose competitor prices |
| **Reliability** | N/A |
| **Performance** | N/A |
| **Cost** | Free (if available) |
| **Maintenance** | N/A |

**Verdict:** Not an option - Ozon API only provides your own product data, not competitor prices.

---

### Option 2: Headless API Scraping (httpx + HTML Parsing)

| Aspect | Assessment |
|--------|------------|
| **Availability** | ✅ **Available** - Ozon product pages are publicly accessible |
| **Reliability** | ⚠️ **Medium** - May break on HTML changes, but easier to fix than Selenium |
| **Performance** | ✅ **Excellent** - ~200-500ms per request vs 5-10s with Selenium |
| **Resource Usage** | ✅ **Minimal** - No browser, just HTTP requests |
| **Parallelization** | ✅ **Excellent** - Can use async/await with connection pooling |
| **Maintenance** | ✅ **Low** - Only CSS selectors need updating |
| **Anti-bot Risk** | ⚠️ **Medium** - Need proper headers, rate limiting, maybe proxy rotation |
| **JavaScript Rendering** | ❌ **Limited** - Only works for server-rendered content |

**Implementation Approach:**
- Use `httpx.AsyncClient` with connection pooling
- Parse HTML with `selectolax` (fast) or `beautifulsoup4`
- Rotate User-Agent headers
- Implement exponential backoff retry logic
- Add rate limiting (respect `PARSER_REQUEST_DELAY_MIN/MAX`)
- Handle Cloudflare/anti-bot challenges

**Verdict:** **RECOMMENDED** - Best balance of performance, maintainability, and reliability.

---

### Option 3: Playwright (Modern Browser Automation)

| Aspect | Assessment |
|--------|------------|
| **Availability** | ✅ **Available** - Modern alternative to Selenium |
| **Reliability** | ✅ **High** - Better auto-wait, more stable selectors |
| **Performance** | ⚠️ **Medium** - Faster than Selenium but still browser-based (~2-3s) |
| **Resource Usage** | ⚠️ **Medium** - Still requires browser process |
| **Parallelization** | ✅ **Good** - Supports async, multiple contexts |
| **Maintenance** | ✅ **Lower** - Auto-updates browsers, better API |
| **Headless Support** | ✅ **Better** - More stable headless mode |
| **Anti-bot** | ⚠️ **Medium** - Still detectable, but stealth plugins available |

**Verdict:** **Good fallback** if httpx approach fails due to JavaScript-rendered content.

---

### Option 4: Third-party Data Providers

| Aspect | Assessment |
|--------|------------|
| **Availability** | ⚠️ **Limited** - Few providers for Russian market/Ozon |
| **Reliability** | ✅ **High** - Professional services |
| **Performance** | ✅ **High** - API-based |
| **Cost** | ❌ **High** - Subscription fees ($100-500+/month) |
| **Dependency** | ❌ **High** - Vendor lock-in, SLA dependency |
| **Data Freshness** | ⚠️ **Variable** - Depends on provider crawl frequency |

**Verdict:** **Not recommended** - Cost and dependency not justified for this use case.

---

## Recommendation

### Primary: **Option 2 - Headless API Scraping (httpx + selectolax)**

**Rationale:**
1. **10-50x faster** than Selenium (200-500ms vs 5-10s per request)
2. **No browser dependency** - runs in any environment (CI/CD, containers, serverless)
3. **Async-native** - easy parallelization with `asyncio.gather` or semaphore
4. **Lower resource usage** - minimal memory/CPU
5. **Easier debugging** - raw HTTP requests/responses, no browser devtools needed
6. **Simpler deployment** - no Chrome, ChromeDriver, or display server needed

**Risk Mitigation:**
- Implement robust retry with exponential backoff
- Rotate User-Agent and headers
- Add configurable rate limiting
- Monitor for HTML structure changes (alert on selector failures)
- Fallback to Playwright if JavaScript rendering becomes necessary

### Fallback: **Option 3 - Playwright**

If httpx approach fails due to:
- Content loaded via JavaScript/AJAX after initial HTML
- Complex anti-bot challenges requiring browser fingerprinting
- Dynamic price updates via WebSocket

---

## Implementation Plan

### Phase 1: Prototype (Week 1)
1. Create `infrastructure/ozon_competitor_new.py` with `OzonPriceParserNew` class
2. Implement `get_price(url)` using `httpx.AsyncClient` + `selectolax`
3. Maintain same interface: `get_price(url) -> float | None`, `close()`, `restart()`
4. Add comprehensive error handling, retries, logging

### Phase 2: Integration (Week 1-2)
1. Create protocol `OzonPriceParserProtocol` in `core/protocols/parser.py`
2. Update DI container to support both parsers via feature flag
3. Modify `ParseCompetitorPricesUseCase` to accept parser via protocol

### Phase 3: A/B Testing (Week 2)
1. Run both parsers in parallel (feature flag)
2. Compare: success rate, latency, accuracy
3. Gradual rollout: 10% → 50% → 100%

### Phase 4: Cleanup (Week 2)
1. Remove Selenium dependencies if successful
2. Update `requirements.txt`, `pyproject.toml`
3. Remove `x_display.py`, `chrome_driver.py`

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Success Rate | ≥ 95% (vs ~80% current) |
| Avg Latency | ≤ 500ms (vs 5-10s current) |
| Resource Usage | ≤ 50MB RAM (vs 200-500MB current) |
| Parallel Requests | 10+ concurrent (vs 1 current) |
| Selector Maintenance | ≤ 1 update/month (vs weekly current) |

---

## Rollback Strategy

If new parser fails to meet criteria:
1. Feature flag `USE_NEW_PARSER=false` immediately reverts to Selenium
2. No code changes needed for rollback
3. Old parser remains in `infrastructure/ozon_competitor.py`
4. Monitor for 1 week before full removal

---

## Appendix: Technical Details

### Current Selectors (to migrate)
```python
price_selectors = [
    'span[data-testid="price-price"]',
    "span.tsHeadline600Large",
    "span.pdp_b0h.tsHeadline600Large",
    "span.pdp_b0h.tsHeadline500Medium",
    'div[data-testid="price"] span',
    'span[class*="tsHeadline"]',
]
```

### Required Headers for httpx
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
```

### Rate Limiting
- Min delay: `settings.PARSER_REQUEST_DELAY_MIN` (default 2.0s)
- Max delay: `settings.PARSER_REQUEST_DELAY_MAX` (default 5.0s)
- Random jitter between requests

---

*Document Version: 1.0*
*Created: 2026-08-25*
*Author: AI Assistant based on codebase analysis*