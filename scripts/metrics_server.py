#!/usr/bin/env python
"""
Prometheus metrics HTTP server for the repricer application.

Run this alongside the Streamlit app to expose /metrics endpoint.
"""

import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from config.settings import settings
from core.metrics import get_metrics_registry  # Import to register metrics

# Initialize metrics
get_metrics_registry()


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint."""

    def do_GET(self) -> None:
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            from core.metrics import get_metrics_registry
            self.wfile.write(generate_latest(get_metrics_registry()))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default log messages
        pass


def run_metrics_server(host: str = "0.0.0.0", port: int = 9090) -> None:
    """Run the metrics HTTP server."""
    server = HTTPServer((host, port), MetricsHandler)
    print(f"Starting metrics server on {host}:{port}")
    print(f"Metrics available at http://{host}:{port}/metrics")
    print(f"Health check at http://{host}:{port}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down metrics server...")
        server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus metrics server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9090, help="Port to bind to")
    args = parser.parse_args()

    run_metrics_server(args.host, args.port)