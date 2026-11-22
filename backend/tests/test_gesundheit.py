"""Prüft, dass die API startet und das Lebenszeichen liefert."""
from fastapi.testclient import TestClient

from api.main import app


def test_gesundheit_meldet_ok():
    """GET /api/gesundheit antwortet mit 200 und status "ok"."""
    antwort = TestClient(app).get("/api/gesundheit")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"
