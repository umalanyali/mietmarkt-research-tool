"""API für Adresssuche, Projektanlage und Umfeld: externe Dienste über respx gemockt."""
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.main import app, sitzung
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.geo import dienste

HAFENSTADT = {"label": "Kaistraße 1, 99999 Hafenstadt", "strasse": "Kaistraße 1", "plz": "99999", "ort": "Hafenstadt",
           "ortsteil": "Neustadt", "lat": 53.5531, "lon": 9.9925}
# Nahe der Demo-Kulisse (rund 300 m vom Lindenquartier)
NAH = {"label": "Teststraße 5, 12345 Musterstadt", "strasse": "Teststraße 5", "plz": "12345", "ort": "Musterstadt",
       "ortsteil": "Nordstadt", "lat": 51.3150, "lon": 9.4810}


def nominatim_antwort(v: dict) -> list:
    """Nominatim-Suchtreffer passend zu einem Vorschlag. Eingabe: Vorschlag. Ausgabe: JSON-Liste."""
    strasse, nr = v["strasse"].rsplit(" ", 1)
    return [{"lat": str(v["lat"]), "lon": str(v["lon"]), "address": {
        "road": strasse, "house_number": nr, "postcode": v["plz"], "city": v["ort"], "suburb": v["ortsteil"]}}]


@pytest.fixture
def client(tmp_path):
    """API gegen eine geseedete Testdatenbank; Drosseln zurückgesetzt. Ausgabe: TestClient."""
    e = engine(tmp_path / "api.db")
    seed(e)
    for d in (dienste.PHOTON_DROSSEL, dienste.NOMINATIM_DROSSEL, dienste.OVERPASS_DROSSEL, dienste.ROUTING_DROSSEL):
        d.zuruecksetzen()

    def test_sitzung():
        """Sitzung auf die Testdatenbank statt auf daten/. Ausgabe: Session (als Generator)."""
        with Session(e) as s:
            yield s

    app.dependency_overrides[sitzung] = test_sitzung
    yield TestClient(app, base_url="http://localhost")
    app.dependency_overrides.clear()


@respx.mock
def test_vorschlaege_mit_attribution(client):
    """GET /api/adressen/vorschlaege liefert Vorschläge und die OSM-Attribution."""
    respx.get(dienste.PHOTON_URL).mock(return_value=httpx.Response(200, json={"features": [
        {"geometry": {"coordinates": [9.9925, 53.5531]}, "properties": {"street": "Kaistraße", "housenumber": "1",
                                                                        "postcode": "99999", "city": "Hafenstadt"}}]}))
    a = client.get("/api/adressen/vorschlaege", params={"q": "Kaistraße 1"}).json()
    assert a["vorschlaege"][0]["label"] == "Kaistraße 1, 99999 Hafenstadt"
    assert a["attribution"] == "© OpenStreetMap-Mitwirkende"


def test_vorschlaege_erst_ab_drei_zeichen(client):
    """Kürzere Suchtexte werden abgewiesen, ohne einen Dienst zu fragen."""
    assert client.get("/api/adressen/vorschlaege", params={"q": "Ju"}).status_code == 422


@respx.mock
def test_dienst_nicht_erreichbar_ist_503(client):
    """Fällt Photon aus, antwortet die API mit 503 und nennt den Dienst."""
    respx.get(dienste.PHOTON_URL).mock(side_effect=httpx.ConnectError("kein Netz"))
    a = client.get("/api/adressen/vorschlaege", params={"q": "Kaistraße"})
    assert a.status_code == 503 and "photon" in a.json()["detail"]


@respx.mock
def test_projekt_anlegen_ohne_marktdaten_im_umkreis(client):
    """Eine Adresse in der fiktiven Hafenstadt wird mit Nominatim-Daten angelegt; im Umkreis liegen keine Comps."""
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=nominatim_antwort(HAFENSTADT)))
    antwort = client.post("/api/projekte", json=HAFENSTADT)
    assert antwort.status_code == 201
    p = antwort.json()
    assert (p["adresse"], p["ort"], p["ortsteil"], p["demo"]) == ("Kaistraße 1", "Hafenstadt", "Neustadt", False)
    assert client.get(f"/api/projekte/{p['id']}/comps").json() == []
    assert client.get(f"/api/projekte/{p['id']}/kennzahlen").json()["kennzahlen"] == []


@respx.mock
def test_echte_adresse_sieht_nie_demo_comps(client):
    """Eine echte Adresse 300 m neben dem Demo-Standort zeigt keine Demo-Comps und keine Comps-Kennzahlen."""
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=nominatim_antwort(NAH)))
    p = client.post("/api/projekte", json=NAH).json()
    assert p["demo"] is False
    assert client.get(f"/api/projekte/{p['id']}/comps").json() == []
    assert client.get(f"/api/projekte/{p['id']}/kennzahlen").json()["comps"]["anzahl"]["wert"] == 0


def test_demo_projekte_sehen_demo_comps_im_umkreis(client):
    """Demo-Projekte sehen die Demo-Comps, soweit sie im Umkreis liegen."""
    assert len(client.get("/api/projekte/1/comps").json()) == 12
    assert 0 < len(client.get("/api/projekte/2/comps").json()) < 12


@respx.mock
def test_projekt_anlegen_faellt_auf_rueckwaertssuche_zurueck(client):
    """Findet Nominatim den Text nicht, liefert die Rückwärtssuche auf die Photon-Koordinaten die Adresse."""
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{dienste.NOMINATIM_URL}/reverse").mock(return_value=httpx.Response(200, json=nominatim_antwort(HAFENSTADT)[0]))
    p = client.post("/api/projekte", json=HAFENSTADT).json()
    assert p["ort"] == "Hafenstadt"


@respx.mock
def test_umfeld_mit_wegezeiten_und_luftlinie_bei_ausfall(client):
    """Umfeld: POIs aus Overpass, Fußzeiten aus OSRM; fällt das Rad-Routing aus, ist die Methode „Luftlinie“."""
    respx.post(url__regex=r"/api/interpreter$").mock(return_value=httpx.Response(200, json={"elements": [
        {"type": "node", "lat": 51.3130, "lon": 9.4800, "tags": {"highway": "bus_stop", "name": "Lindenplatz"}}]}))
    respx.get(url__startswith=dienste.ROUTING_URL["fuss"]).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, 120.0]], "distances": [[0, 150.0]]}))
    respx.get(url__startswith=dienste.ROUTING_URL["rad"]).mock(return_value=httpx.Response(503))
    u = client.get("/api/projekte/1/umfeld").json()
    poi = u["pois"][0]
    assert poi["name"] == "Lindenplatz" and poi["zu_fuss"]["wert"] == pytest.approx(2.0)
    assert poi["rad"] is None and poi["methode_rad"] == "Luftlinie"
    assert poi["luftlinie"]["herkunft"] == "berechnet" and u["attribution"] == "© OpenStreetMap-Mitwirkende"


@respx.mock
def test_umfeld_overpass_ausfall_ist_503(client):
    """Antwortet Overpass nicht, gibt es kein Umfeld, sondern 503 (alle Server aus der Konfig ausgefallen)."""
    respx.post(url__regex=r"/api/interpreter$").mock(return_value=httpx.Response(504))
    assert client.get("/api/projekte/1/umfeld").status_code == 503


# ------------------------------------------------------------------ Befunde aus den Reviews (P1–P4, S2)

FERN = {"label": "Feldweg 3, 99998 Fernstadt", "strasse": "Feldweg 3", "plz": "99998", "ort": "Fernstadt",
        "ortsteil": "Unterdorf", "lat": 53.0, "lon": 10.0}


@respx.mock
def test_osrm_null_dauer_faellt_auf_luftlinie_zurueck(client):
    """P1: Ein nicht routbares Ziel (OSRM liefert null) ergibt Luftlinie statt HTTP 500."""
    respx.post(url__regex=r"/api/interpreter$").mock(return_value=httpx.Response(200, json={"elements": [
        {"type": "node", "lat": 51.3130, "lon": 9.4800, "tags": {"highway": "bus_stop", "name": "Lindenplatz"}}]}))
    respx.get(url__startswith=dienste.ROUTING_URL["fuss"]).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, None]], "distances": [[0, None]]}))
    respx.get(url__startswith=dienste.ROUTING_URL["rad"]).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, 60.0]], "distances": [[0, 150.0]]}))
    antwort = client.get("/api/projekte/1/umfeld")
    assert antwort.status_code == 200
    poi = antwort.json()["pois"][0]
    assert poi["zu_fuss"] is None and poi["methode_fuss"] == "Luftlinie" and poi["methode_rad"] == "Route"


@respx.mock
def test_vorschlaege_ohne_strasse_ergeben_getrennte_projekte(client):
    """P4: Zwei Orte ohne Straße (leere Adresse) dürfen nicht zum selben Projekt zusammenfallen."""
    a = {**FERN, "label": "Marktplatz, 99998 Fernstadt", "strasse": "", "lat": 53.001}
    b = {**FERN, "label": "Bahnhof, 99998 Fernstadt", "strasse": "", "lat": 53.002}
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{dienste.NOMINATIM_URL}/reverse").mock(return_value=httpx.Response(200, json={}))
    assert client.post("/api/projekte", json=a).json()["id"] != client.post("/api/projekte", json=b).json()["id"]


@respx.mock
def test_gleiche_adresse_wie_demo_ergibt_kein_demo_projekt(client):
    """P4: Eine echte Adresse, die zufällig wie die Demo-Adresse heißt, bekommt ein eigenes, echtes Projekt."""
    demo_gleich = {"label": "Lindenallee 30, 12345 Musterstadt", "strasse": "Lindenallee 30", "plz": "12345",
                   "ort": "Musterstadt", "ortsteil": "Nordstadt", "lat": 51.3127, "lon": 9.4797}
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=nominatim_antwort(demo_gleich)))
    p = client.post("/api/projekte", json=demo_gleich).json()
    assert p["demo"] is False and p["id"] != 1


@pytest.mark.parametrize("feld,wert", [("lat", 1e308), ("lon", -200.0), ("lat", 40.0), ("label", "x" * 201), ("plz", "1" * 11)])
def test_vorschlag_ausserhalb_der_grenzen_wird_abgewiesen(client, feld, wert):
    """S2/S3: Koordinaten außerhalb Deutschlands und überlange Texte werden mit 422 abgewiesen."""
    assert client.post("/api/projekte", json={**FERN, feld: wert}).status_code == 422


def test_nan_als_koordinate_wird_abgewiesen(client):
    """S2: NaN ist keine Koordinate."""
    roh = '{"label": "Feldweg 3", "strasse": "Feldweg 3", "plz": "99998", "ort": "Fernstadt", "ortsteil": "", "lat": NaN, "lon": 10.0}'
    assert client.post("/api/projekte", content=roh, headers={"Content-Type": "application/json"}).status_code == 422


def test_suchtext_hoechstens_200_zeichen(client):
    """S3: überlange Suchtexte gehen nicht an Photon."""
    assert client.get("/api/adressen/vorschlaege", params={"q": "a" * 201}).status_code == 422
