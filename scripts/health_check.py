#!/usr/bin/env python
"""
Health check script for Repricer-Ozon.

Provides readiness/liveness probes for systemd/k8s deployments.
Checks: database connectivity, API credentials, disk space, log directory.
"""

import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from infrastructure.db.repository import SQLiteRepository


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
        import shutil

        data_dir = Path(settings.DATA_FILE).parent
        log_dir = Path(settings.DATA_FILE).parent.parent / "logs"

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
        excel_path = settings.DATA_FILE_PATH
        if not excel_path.exists():
            return {"status": "degraded", "details": f"Excel file not found: {excel_path}"}

        # Try to open it
        import openpyxl

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
        log_dir = Path(settings.DATA_FILE).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Test write
        test_file = log_dir / ".health_check_write_test"
        test_file.write_text("ok")
        test_file.unlink()

        return {"status": "healthy", "details": "Log directory writable"}
    except Exception as e:
        return {"status": "unhealthy", "details": f"Log directory error: {e}"}


def run_checks() -> dict[str, Any]:
    """Run all health checks."""
    checks = {
        "database": check_database(),
        "api_credentials": check_api_credentials(),
        "disk_space": check_disk_space(),
        "excel_file": check_excel_file(),
        "log_directory": check_log_directory(),
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


def main():
    """Main entry point."""
    import argparse
    import json

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
