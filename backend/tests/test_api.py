"""HTTP-API: Projekte, Comps und Kennzahlen aus der Demo-Datenbank, jede Zahl mit Herkunft."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.main import app, sitzung
from mietmarkt.db import engine
from mietmarkt.demo import seed


@pytest.fixture
def client(tmp_path):
    """API gegen eine frisch geseedete Testdatenbank. Eingabe: tmp_path. Ausgabe: TestClient."""
    e = engine(tmp_path / "api.db")
    seed(e)

    def test_sitzung():
        with Session(e) as s:
            yield s

    app.dependency_overrides[sitzung] = test_sitzung
    yield TestClient(app, base_url="http://localhost")
    app.dependency_overrides.clear()


def test_projekte_liste(client):
    """GET /api/projekte liefert alle Projekte mit Adresse und Koordinaten."""
    daten = client.get("/api/projekte").json()
    assert [p["name"] for p in daten] == ["Lindenquartier", "Hafenblock", "Am Stadtpark"]
    assert {"adresse", "lat", "lon", "stichtag"} <= daten[0].keys()


def test_projekt_mit_quellen_und_404(client):
    """GET /api/projekte/{id} liefert das Projekt samt Datenstand je Quelle; unbekannte ID gibt 404."""
    p = client.get("/api/projekte/1").json()
    assert p["name"] == "Lindenquartier" and {q["name"] for q in p["quellen"]} >= {"RIWIS", "VALUE"}
    assert client.get("/api/projekte/999").status_code == 404


def test_comps_mit_berechneten_werten(client):
    """Comps tragen €/m², Anfragen je Monat und Entfernung als Werte mit Rechenweg."""
    comps = client.get("/api/projekte/1/comps").json()
    assert len(comps) == 12
    c1 = comps[0]
    assert c1["eur_qm"]["wert"] == pytest.approx(1012 / 58.4)
    assert c1["eur_qm"]["herkunft"] == "berechnet" and "€" in c1["eur_qm"]["rechenweg_text"]
    assert c1["tage_online"]["wert"] == 34 and "Stichtag" in c1["tage_online"]["rechenweg_text"]
    assert c1["entfernung_km"]["einheit"] == "km" and "Luftlinie" in c1["entfernung_km"]["rechenweg_text"]
    sechs = next(c for c in comps if c["nr"] == 6)
    assert sechs["anfragen_monat"]["wert"] is None  # nur 5 Tage online


def test_kennzahlen_mit_zusammenfassung(client):
    """Kennzahlen: Marktwerte aus dem Import plus berechnete Comps-Zusammenfassung und Preisklassen."""
    k = client.get("/api/projekte/1/kennzahlen").json()
    assert {x["gruppe"] for x in k["kennzahlen"]} >= {"soziodemografie", "zeitreihe", "value", "weitere"}
    assert k["comps"]["regel_eg"]["wert"] == pytest.approx(16.96, abs=0.005)
    assert k["comps"]["dg"]["wert"] == pytest.approx(19.16, abs=0.005)
    assert k["comps"]["anfragen_monat"]["wert"] == pytest.approx(24.1, abs=0.05)
    assert k["preisklassen"]["summe"]["wert"] == 105
    assert all(x["herkunft"] for x in k["kennzahlen"])


def test_projekt_ohne_eigene_kennzahlen_sieht_nur_comps_im_umkreis(client):
    """Hafenblock hat keine eigenen Kennzahlen; Comps zeigt es nur, soweit sie im Umkreis von 2 km liegen."""
    k = client.get("/api/projekte/2/kennzahlen").json()
    assert k["kennzahlen"] == []
    comps = client.get("/api/projekte/2/comps").json()
    assert len(comps) < 12 and all(c["entfernung_km"]["wert"] <= 2 for c in comps)


@pytest.mark.parametrize(("origin", "erwartet"), [
    ("https://angreifer.example", 403), ("null", 403),  # fremde Website bzw. Sandbox-iframe/Datei
    ("http://localhost:5173", 404), ("http://127.0.0.1:8000", 404), (None, 404),  # eigene Oberfläche, curl, Tests
])
def test_post_nur_von_eigener_herkunft(client, origin, erwartet):
    """CSRF-Schutz: Schreibende Anfragen mit fremdem Origin weist die API ab, bevor ein Endpunkt läuft (sonst könnte
    jede Website z. B. ein Dokument mit KI-Freigabe hochladen). 404: Anfrage kam durch, Projekt 999 gibt es nicht."""
    kopf = {"Origin": origin} if origin else {}
    assert client.post("/api/projekte/999/laeufe", headers=kopf).status_code == erwartet
    assert client.get("/api/projekte", headers=kopf).status_code == 200  # Lesen bleibt erlaubt (Antwort sperrt CORS)
