"""Prüft, dass die API startet und das Lebenszeichen liefert."""
from fastapi.testclient import TestClient

from api.main import app


def test_gesundheit_meldet_ok():
    """GET /api/gesundheit antwortet mit 200 und status "ok"."""
    antwort = TestClient(app, base_url="http://localhost").get("/api/gesundheit")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"


def test_fremder_host_wird_abgewiesen():
    """F: Schutz vor DNS-Rebinding – eine fremde Domain, die auf 127.0.0.1 zeigt, bekommt keine Daten."""
    assert TestClient(app, base_url="http://angreifer.example").get("/api/gesundheit").status_code == 400
    assert TestClient(app, base_url="http://127.0.0.1:8000").get("/api/gesundheit").status_code == 200
