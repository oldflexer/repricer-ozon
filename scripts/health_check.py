#!/usr/bin/env python
"""
Health check script for Repricer-Ozon.

Provides readiness/liveness probes for systemd/k8s deployments.
Checks: database connectivity, API credentials, disk space, log directory.
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import openpyxl

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from infrastructure.db.repository import SQLiteRepository
from infrastructure.ozon_api import OzonApiClient


def check_database() -> dict[str, Any]:
    """Check SQLite database connectivity and basic structure."""
    try:
        repo = SQLiteRepository()
        products = repo.get_all_products()
        return {"status": "healthy", "details": f"DB accessible, {len(products)} products loaded"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Database error: {e}"}


def check_api_credentials() -> dict[str, Any]:
    """Check if Ozon API credentials are configured."""
    if not settings.OZON_CLIENT_ID or not settings.OZON_API_KEY:
        return {"status": "unhealthy", "details": "OZON_CLIENT_ID or OZON_API_KEY not configured"}

    if settings.OZON_CLIENT_ID == "your_client_id" or settings.OZON_API_KEY == "your_api_key":
        return {"status": "degraded", "details": "API credentials appear to be placeholder values"}

    return {"status": "healthy", "details": "API credentials configured"}


def check_disk_space() -> dict[str, Any]:
    """Check disk space for data and logs directories."""
    try:
        data_dir = Path(settings.data_file_path).parent
        log_dir = Path(settings.data_file_path).parent.parent / "logs"

        results = {}
        for name, path in [("data", data_dir), ("logs", log_dir)]:
            if path.exists():
                total, used, free = shutil.disk_usage(path)
                free_gb = free / (1024**3)
                if free_gb < 1.0:
                    results[name] = f"LOW SPACE: {free_gb:.2f} GB free"
                else:
                    results[name] = f"OK: {free_gb:.2f} GB free"
            else:
                results[name] = "DIR NOT EXISTS"

        all_ok = all("OK" in v for v in results.values())
        return {"status": "healthy" if all_ok else "degraded", "details": f"Disk: {results}"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Disk check failed: {e}"}


def check_excel_file() -> dict[str, Any]:
    """Check Excel data file accessibility."""
    try:
        excel_path = settings.data_file_path
        if not excel_path.exists():
            return {"status": "degraded", "details": f"Excel file not found: {excel_path}"}

        # Try to open it
        wb = openpyxl.load_workbook(excel_path, read_only=True)
        wb.close()

        return {"status": "healthy", "details": f"Excel file accessible: {excel_path}"}
    except PermissionError:
        return {"status": "unhealthy", "details": "Excel file locked or permission denied"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Excel check failed: {e}"}


def check_log_directory() -> dict[str, Any]:
    """Check log directory exists and is writable."""
    try:
        log_dir = Path(settings.data_file_path).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Test write
        test_file = log_dir / ".health_check_write_test"
        test_file.write_text("ok")
        test_file.unlink()

        return {"status": "healthy", "details": "Log directory writable"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Log directory error: {e}"}


def check_api_connectivity() -> dict[str, Any]:
    """Check Ozon API connectivity with a simple request."""
    try:
        if not settings.OZON_CLIENT_ID or not settings.OZON_API_KEY:
            return {"status": "unhealthy", "details": "API credentials not configured"}

        client = OzonApiClient()
        # Try a simple API call - get product list with limit 1
        import asyncio
        result = asyncio.run(client.get_product_ids_by_skus(["health_check_test"]))
        return {"status": "healthy", "details": "API connectivity OK"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"API connectivity failed: {e}"}


def check_last_run_time() -> dict[str, Any]:
    """Check when the last repricing cycle ran."""
    try:
        repo = SQLiteRepository()
        last_run = repo.get_last_run_time()
        if last_run is None:
            return {"status": "degraded", "details": "No previous run recorded"}

        # Check if last run was within expected timeframe (e.g., 24 hours)
        elapsed_hours = (time.time() - last_run.timestamp()) / 3600
        if elapsed_hours > 24:
            return {"status": "degraded", "details": f"Last run {elapsed_hours:.1f} hours ago (>24h)"}

        return {"status": "healthy", "details": f"Last run {elapsed_hours:.1f} hours ago"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Last run check failed: {e}"}


def run_checks() -> dict[str, Any]:
    """Run all health checks."""
    checks = {
        "database": check_database(),
        "api_credentials": check_api_credentials(),
        "api_connectivity": check_api_connectivity(),
        "disk_space": check_disk_space(),
        "excel_file": check_excel_file(),
        "log_directory": check_log_directory(),
        "last_run_time": check_last_run_time(),
    }

    # Overall status
    statuses = [c["status"] for c in checks.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return {"status": overall, "checks": checks}


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Health check for Repricer-Ozon")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    result = run_checks()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Overall status: {result['status'].upper()}")
        print()
        for name, check in result["checks"].items():
            status = check["status"].upper()
            details = check["details"]
            print(f"  [{status}] {name}: {details}")

    # Exit code for monitoring systems
    if result["status"] == "healthy":
        sys.exit(0)
    elif result["status"] == "degraded":
        sys.exit(1)  # Warning
    else:
        sys.exit(2)  # Critical


if __name__ == "__main__":
    main()
