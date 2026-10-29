"""Smoke-test an isolated cloud container using only fake CI credentials."""
from __future__ import annotations

import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    base = sys.argv[1].rstrip("/")
    for attempt in range(60):
        try:
            with urlopen(base + "/health/ready", timeout=3) as response:
                assert json.load(response)["status"] == "ok"
            break
        except (HTTPError, URLError, TimeoutError, ConnectionError):
            if attempt == 59:
                raise RuntimeError("Cloud container did not become ready") from None
            time.sleep(2)

    with urlopen(base + "/", timeout=10) as response:
        assert response.headers["content-type"].startswith("text/html")
        assert '<div id="root">' in response.read().decode()
    try:
        urlopen(base + "/api/me", timeout=10)
        raise AssertionError("Unauthenticated API access must be rejected")
    except HTTPError as error:
        assert error.code == 401

    request = Request(base + "/api/auth/login", method="POST", headers={"Content-Type": "application/json"},
                      data=json.dumps({"email": "operador@demo.local", "password": "demo-operador"}).encode())
    with urlopen(request, timeout=10) as response:
        token = json.load(response)["access_token"]
    request = Request(base + "/api/me", headers={"Authorization": "Bearer " + token})
    with urlopen(request, timeout=10) as response:
        assert json.load(response)["email"] == "operador@demo.local"
    print("Cloud smoke check passed: PostgreSQL migrations, dashboard and authenticated API")


if __name__ == "__main__":
    main()
