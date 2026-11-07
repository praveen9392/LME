"""
Local Web Server for the Setup Wizard and Live Analytics Dashboard.
Binds strictly to 127.0.0.1 to prevent unauthorized external network access.
"""
from __future__ import annotations

from http.server import HTTPServer
import threading
import time
import webbrowser

from backend.core.logging import get_logger
from backend.web.handlers import WebHandler

logger = get_logger(__name__)

DEFAULT_PORT = 8765
BIND_HOST = "127.0.0.1"


def run_web_server(port: int = DEFAULT_PORT, target_path: str = "/setup", block_until_done: bool = True) -> None:
    """
    Initializes and starts the local web server, opening the target URL in the default browser.
    """
    shutdown_event = threading.Event()
    WebHandler.shutdown_event = shutdown_event

    server = HTTPServer((BIND_HOST, port), WebHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://{BIND_HOST}:{port}{target_path}"
    logger.info("Local Web Server running at %s", url)
    print(f"\n  NopeRi Web UI -> opening {url}")
    print("  Complete setup or review dashboard in your browser.\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    if block_until_done:
        try:
            shutdown_event.wait()
            logger.info("Web setup completed — shutting down server")
        except KeyboardInterrupt:
            logger.info("Web server interrupted by user")
        finally:
            server.shutdown()
            print("  Web server stopped.\n")
    else:
        # Run until Ctrl+C
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()


def launch_wizard(port: int = DEFAULT_PORT) -> None:
    """Public helper to launch the 5-step configuration wizard."""
    run_web_server(port=port, target_path="/setup", block_until_done=True)


def launch_dashboard(port: int = DEFAULT_PORT) -> None:
    """Public helper to open the live analytics dashboard."""
    run_web_server(port=port, target_path="/dashboard", block_until_done=False)
