"""The static frontend is served by the API app and never uses prohibited selection wording."""

import re

from app.main import STATIC_DIR

PROHIBITED = re.compile(r"\b(winner|best|recommend\w*|choos\w*|choice|hire\w*|select\w*)\b", re.IGNORECASE)


def test_index_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "VendorMatch AI" in r.text and "Try Demo" in r.text


def test_assets_are_served(client):
    for path, kind in (("/css/styles.css", "text/css"), ("/js/app.js", "javascript"), ("/js/views/vendor.js", "javascript")):
        r = client.get(path)
        assert r.status_code == 200, path
        assert kind in r.headers["content-type"], path


def test_api_routes_take_precedence_over_static_files(client):
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_frontend_sources_use_neutral_wording():
    offenders = []
    for path in STATIC_DIR.rglob("*"):
        if path.suffix in {".html", ".js", ".css"}:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if PROHIBITED.search(line):
                    offenders.append(f"{path.relative_to(STATIC_DIR)}:{n}: {line.strip()}")
    assert offenders == []


def test_backend_texts_shown_in_the_ui_use_neutral_wording(make_client):
    client = make_client()
    pid = client.post("/api/demo").json()["project_id"]
    for path in (f"/api/projects/{pid}/comparison", f"/api/projects/{pid}/analysis"):
        body = client.get(path).text
        assert not PROHIBITED.search(body), PROHIBITED.search(body)


def test_static_files_are_revalidated_after_deploys(client):
    for path in ("/", "/js/app.js", "/js/views/vendor.js", "/css/styles.css"):
        r = client.get(path)
        assert r.headers["cache-control"] == "no-cache", path
        assert "etag" in r.headers, path
    etag = client.get("/js/app.js").headers["etag"]
    assert client.get("/js/app.js", headers={"If-None-Match": etag}).status_code == 304
