"""
Prometheus metrics for the repricer application.
"""

from prometheus_client import Counter, Gauge, Histogram

# Pipeline metrics
repricer_cycle_duration_seconds = Histogram(
    "repricer_cycle_duration_seconds",
    "Duration of repricing cycle in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

repricer_products_loaded = Gauge(
    "repricer_products_loaded",
    "Number of products loaded in the last cycle",
)

repricer_prices_updated = Counter(
    "repricer_prices_updated_total",
    "Total number of prices updated",
    ["status"],  # success, failed, dry_run
)

repricer_errors_total = Counter(
    "repricer_errors_total",
    "Total number of errors by type",
    ["error_type", "step"],
)

repricer_marginality = Gauge(
    "repricer_marginality",
    "Marginality by SKU",
    ["sku"],
)

# Ozon API metrics
ozon_api_request_duration_seconds = Histogram(
    "ozon_api_request_duration_seconds",
    "Duration of Ozon API requests in seconds",
    ["endpoint"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

ozon_api_errors_total = Counter(
    "ozon_api_errors_total",
    "Total number of Ozon API errors",
    ["endpoint", "error_code"],
)

ozon_api_circuit_breaker_state = Gauge(
    "ozon_api_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["endpoint"],
)

# Generic Circuit Breaker metrics (for any service)
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["name"],
)

circuit_breaker_failures_total = Counter(
    "circuit_breaker_failures_total",
    "Total number of circuit breaker failures",
    ["name"],
)

circuit_breaker_successes_total = Counter(
    "circuit_breaker_successes_total",
    "Total number of circuit breaker successes",
    ["name"],
)

circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Total number of circuit breaker state changes",
    ["name", "from_state", "to_state"],
)

# Parser metrics
parser_price_fetch_duration_seconds = Histogram(
    "parser_price_fetch_duration_seconds",
    "Duration of competitor price fetching in seconds",
    buckets=[1, 5, 10, 30, 60, 120],
)

parser_price_fetch_errors_total = Counter(
    "parser_price_fetch_errors_total",
    "Total number of parser price fetch errors",
    ["error_type"],
)

# Database metrics
db_operations_duration_seconds = Histogram(
    "db_operations_duration_seconds",
    "Duration of database operations in seconds",
    ["operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5],
)

db_errors_total = Counter(
    "db_errors_total",
    "Total number of database errors",
    ["operation", "error_type"],
)

# Excel metrics
excel_operations_duration_seconds = Histogram(
    "excel_operations_duration_seconds",
    "Duration of Excel operations in seconds",
    ["operation"],
    buckets=[0.1, 0.5, 1, 5, 10, 30],
)

excel_errors_total = Counter(
    "excel_errors_total",
    "Total number of Excel errors",
    ["operation", "error_type"],
)


def record_cycle_duration(duration: float) -> None:
    """Record the duration of a repricing cycle."""
    repricer_cycle_duration_seconds.observe(duration)


def record_products_loaded(count: int) -> None:
    """Record the number of products loaded."""
    repricer_products_loaded.set(count)


def record_prices_updated(status: str, count: int = 1) -> None:
    """Record the number of prices updated."""
    repricer_prices_updated.labels(status=status).inc(count)


def record_error(error_type: str, step: str) -> None:
    """Record an error."""
    repricer_errors_total.labels(error_type=error_type, step=step).inc()


def record_marginality(sku: str, marginality: float) -> None:
    """Record marginality for a SKU."""
    repricer_marginality.labels(sku=sku).set(marginality)


def record_ozon_api_request(endpoint: str, duration: float) -> None:
    """Record Ozon API request duration."""
    ozon_api_request_duration_seconds.labels(endpoint=endpoint).observe(duration)


def record_ozon_api_error(endpoint: str, error_code: str) -> None:
    """Record Ozon API error."""
    ozon_api_errors_total.labels(endpoint=endpoint, error_code=error_code).inc()


def set_circuit_breaker_state(endpoint: str, state: int) -> None:
    """Set circuit breaker state (0=closed, 1=open, 2=half-open)."""
    ozon_api_circuit_breaker_state.labels(endpoint=endpoint).set(state)


def record_parser_price_fetch(duration: float) -> None:
    """Record parser price fetch duration."""
    parser_price_fetch_duration_seconds.observe(duration)


def record_parser_price_fetch_error(error_type: str) -> None:
    """Record parser price fetch error."""
    parser_price_fetch_errors_total.labels(error_type=error_type).inc()


def record_db_operation(operation: str, duration: float) -> None:
    """Record database operation duration."""
    db_operations_duration_seconds.labels(operation=operation).observe(duration)


def record_db_error(operation: str, error_type: str) -> None:
    """Record database error."""
    db_errors_total.labels(operation=operation, error_type=error_type).inc()


def record_excel_operation(operation: str, duration: float) -> None:
    """Record Excel operation duration."""
    excel_operations_duration_seconds.labels(operation=operation).observe(duration)


def record_excel_error(operation: str, error_type: str) -> None:
    """Record Excel error."""
    excel_errors_total.labels(operation=operation, error_type=error_type).inc()