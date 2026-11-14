"""Guards the layering this boilerplate exists to demonstrate."""

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _sources(folder: str):
    return {p.name: p.read_text(encoding="utf-8") for p in (APP / folder).rglob("*.py")}


def test_routes_do_not_touch_the_database_or_vendor_sdks():
    for name, source in _sources("api/v1/routes").items():
        for forbidden in ("sqlalchemy", "groq", "pinecone", "app.repositories", "app.db"):
            assert forbidden not in source, f"routes/{name} imports {forbidden}"


def test_services_do_not_use_http_or_vendor_sdks():
    for name, source in _sources("services").items():
        for forbidden in ("fastapi", "HTTPException", "import groq", "import pinecone"):
            assert forbidden not in source, f"services/{name} uses {forbidden}"
