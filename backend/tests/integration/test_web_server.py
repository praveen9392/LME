"""
Integration tests for local web server and request handlers.
"""
from io import BytesIO
from unittest.mock import MagicMock
from backend.web.handlers import WebHandler


def test_web_handler_routes():
    handler = WebHandler.__new__(WebHandler)
    handler.client_address = ("127.0.0.1", 54321)
    handler.rfile = BytesIO(b"{}")
    handler.wfile = BytesIO()
    handler.headers = {"Content-Length": "0"}

    # Mock response methods
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    # 1. Test /api/config
    handler.path = "/api/config"
    handler.do_GET()
    handler.send_response.assert_called_with(200)

    # 2. Test /dashboard template
    handler.send_response.reset_mock()
    handler.path = "/dashboard"
    handler.do_GET()
    handler.send_response.assert_called_with(200)

    # 3. Test 404 unknown path
    handler.send_response.reset_mock()
    handler.path = "/nonexistent-path"
    handler.do_GET()
    handler.send_response.assert_called_with(404)
