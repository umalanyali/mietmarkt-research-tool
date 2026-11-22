"""Geodienste (Photon, Nominatim, Overpass, OSRM): nur gegen respx-Mocks, nie echt. Drosselung, Cache, Ausfälle."""
import asyncio
import datetime as dt
import itertools
import threading
import time

import httpx
import pytest
import respx
from sqlmodel import Session, select

from mietmarkt.db import engine
from mietmarkt.geo import cache, dienste
from mietmarkt.geo.dienste import (
    DienstNichtErreichbar,
    Drossel,
    geokodieren,
    rueckwaerts,
    umfeld_pois,
    vorschlaege,
    wegezeiten,
)
from mietmarkt.geo.umfeld import umfeld
from mietmarkt.modelle import GeoCache

PHOTON = {"features": [{"geometry": {"coordinates": [9.4881, 51.3116]}, "properties": {
    "street": "Lindenallee", "housenumber": "10", "postcode": "12345", "city": "Musterstadt", "district": "Mitte"}}]}
NOMINATIM_SUCHE = [{"lat": "51.3116", "lon": "9.4881", "address": {
    "road": "Lindenallee", "house_number": "10", "postcode": "12345", "city": "Musterstadt", "suburb": "Mitte"}}]


@pytest.fixture
def s(tmp_path):
    """Leere Testdatenbank für den Cache. Ausgabe: Session."""
    with Session(engine(tmp_path / "geo.db")) as sitzung:
        yield sitzung


@pytest.fixture(autouse=True)
def drosseln_zuruecksetzen():
    """Jeder Test beginnt ohne Wartezeit aus dem vorherigen Test."""
    for d in (dienste.PHOTON_DROSSEL, dienste.NOMINATIM_DROSSEL, dienste.OVERPASS_DROSSEL, dienste.ROUTING_DROSSEL):
        d.zuruecksetzen()


@respx.mock
def test_photon_vorschlaege_mit_ortsteil_und_parametern(s):
    """Photon wird mit lang=de, limit=5 und Deutschland-bbox gefragt; Vorschläge tragen PLZ, Ort und Ortsteil."""
    route = respx.get(dienste.PHOTON_URL).mock(return_value=httpx.Response(200, json=PHOTON))
    v = asyncio.run(vorschlaege("Lindenallee 10", s))
    assert v[0].label == "Lindenallee 10, 12345 Musterstadt" and v[0].ortsteil == "Mitte"
    params = route.calls[0].request.url.params
    assert (params["lang"], params["limit"], params["bbox"]) == ("de", "5", dienste.BBOX_DE)


@respx.mock
def test_gleiche_anfrage_zweimal_ist_ein_externer_aufruf(s):
    """Cache: die zweite identische Anfrage kommt aus dem Cache (Tabelle geocache)."""
    route = respx.get(dienste.PHOTON_URL).mock(return_value=httpx.Response(200, json=PHOTON))
    asyncio.run(vorschlaege("Lindenallee 10", s))
    asyncio.run(vorschlaege("Lindenallee 10", s))
    assert route.call_count == 1
    assert len(s.exec(select(GeoCache)).all()) == 1


@respx.mock
def test_abgelaufener_cache_fragt_neu(s):
    """Einträge älter als 30 Tage gelten nicht mehr."""
    route = respx.get(dienste.PHOTON_URL).mock(return_value=httpx.Response(200, json=PHOTON))
    asyncio.run(vorschlaege("Lindenallee 10", s))
    eintrag = s.exec(select(GeoCache)).one()
    eintrag.abgerufen_am = dt.datetime.now(dt.UTC) - dt.timedelta(days=31)
    s.add(eintrag)
    s.commit()
    asyncio.run(vorschlaege("Lindenallee 10", s))
    assert route.call_count == 2


@respx.mock
def test_nominatim_hoechstens_eine_anfrage_pro_sekunde(s):
    """Zwei verschiedene Nominatim-Anfragen liegen mindestens 1 s auseinander; User-Agent und Sprache stimmen."""
    zeiten = []

    def antwort(request):
        """Merkt sich den Zeitpunkt und prüft die Kopfzeilen. Eingabe: Anfrage. Ausgabe: Nominatim-Antwort."""
        zeiten.append(time.monotonic())
        assert request.headers["User-Agent"] == dienste.USER_AGENT and request.headers["Accept-Language"] == "de"
        return httpx.Response(200, json=NOMINATIM_SUCHE)

    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(side_effect=antwort)

    async def zwei_gleichzeitig():
        """Startet zwei verschiedene Geokodierungen gleichzeitig. Ausgabe: keine."""
        await asyncio.gather(geokodieren("Adresse A", s), geokodieren("Adresse B", s))

    asyncio.run(zwei_gleichzeitig())
    assert len(zeiten) == 2 and zeiten[1] - zeiten[0] >= 1.0


@respx.mock
def test_geokodieren_und_rueckwaerts(s):
    """Nominatim liefert Adresse, PLZ, Ort und Ortsteil; die Rückwärtssuche dasselbe für Koordinaten."""
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=NOMINATIM_SUCHE))
    respx.get(f"{dienste.NOMINATIM_URL}/reverse").mock(return_value=httpx.Response(200, json=NOMINATIM_SUCHE[0]))
    ort = asyncio.run(geokodieren("Lindenallee 10, 12345 Musterstadt", s))
    assert (ort.adresse, ort.plz, ort.ort, ort.ortsteil) == ("Lindenallee 10", "12345", "Musterstadt", "Mitte")
    assert asyncio.run(rueckwaerts(51.3116, 9.4881, s)).lat == pytest.approx(51.3116)


@respx.mock
def test_nichts_gefunden_ist_none(s):
    """Eine leere Trefferliste ist kein Fehler, sondern None."""
    respx.get(f"{dienste.NOMINATIM_URL}/search").mock(return_value=httpx.Response(200, json=[]))
    assert asyncio.run(geokodieren("gibt es nicht", s)) is None


@respx.mock
def test_overpass_kategorien_im_radius(s):
    """Overpass-Elemente werden den Kategorien zugeordnet; Wege nutzen ihren Mittelpunkt; ohne Namen gibt es einen Ersatz."""
    elemente = [
        {"type": "node", "lat": 51.312, "lon": 9.481, "tags": {"highway": "bus_stop", "name": "Lindenplatz"}},
        {"type": "way", "center": {"lat": 51.313, "lon": 9.482}, "tags": {"shop": "supermarket", "name": "Markt"}},
        {"type": "node", "lat": 51.314, "lon": 9.483, "tags": {"amenity": "kindergarten"}},
    ]
    route = respx.post(dienste.OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": elemente}))
    pois = asyncio.run(umfeld_pois(51.3116, 9.4881, s))
    assert [(p.kategorie, p.name) for p in pois] == [("ÖPNV", "Lindenplatz"), ("Supermarkt", "Markt"), ("Kita", "Kita")]
    assert "around:1000" in route.calls[0].request.content.decode().replace("%3A", ":")


@respx.mock
def test_wegezeiten_fuss_und_rad_mit_ausfall(s):
    """Fuß kommt von OSRM; fällt der Rad-Dienst aus, ist das Ergebnis dafür None (Aufrufer nutzt Luftlinie)."""
    respx.get(url__startswith=dienste.ROUTING_URL["fuss"]).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, 582.1]], "distances": [[0, 728.2]]}))
    respx.get(url__startswith=dienste.ROUTING_URL["rad"]).mock(return_value=httpx.Response(503))
    z = asyncio.run(wegezeiten((51.3116, 9.4881), [(51.3155, 9.4850)], s))
    assert z["fuss"] == [(582.1, 728.2, dt.date.today())] and z["rad"] is None


@respx.mock
def test_dienstausfall_wird_gemeldet(s):
    """Ein 500er oder Netzwerkfehler wird zu DienstNichtErreichbar, nichts landet im Cache."""
    respx.get(dienste.PHOTON_URL).mock(side_effect=httpx.ConnectError("kein Netz"))
    with pytest.raises(DienstNichtErreichbar):
        asyncio.run(vorschlaege("Lindenallee 10", s))
    assert s.exec(select(GeoCache)).all() == []


@respx.mock
def test_overpass_hat_keinen_rueckfall_server(s):
    """S5: Fällt Overpass aus, gehen die Koordinaten an keinen weiteren Server, sondern es gibt DienstNichtErreichbar."""
    route = respx.post(dienste.OVERPASS_URL).mock(return_value=httpx.Response(504))
    with pytest.raises(DienstNichtErreichbar):
        asyncio.run(umfeld_pois(51.3116, 9.4881, s))
    assert route.call_count == 1 and len(respx.calls) == 1


@respx.mock
def test_gleichzeitige_gleiche_anfragen_sind_ein_aufruf(s):
    """P2: Zwei gleiche Anfragen zur selben Zeit gehen nur einmal nach außen; die zweite wartet auf den Cache."""
    async def langsam(request):
        """Antwortet nach 0,2 s, damit sich beide Anfragen überlappen. Eingabe: Anfrage. Ausgabe: Photon-Antwort."""
        await asyncio.sleep(0.2)
        return httpx.Response(200, json=PHOTON)

    route = respx.get(dienste.PHOTON_URL).mock(side_effect=langsam)

    async def zwei():
        """Startet dieselbe Suche zweimal gleichzeitig. Ausgabe: beide Ergebnisse."""
        return await asyncio.gather(vorschlaege("Lindenallee 30", s), vorschlaege("Lindenallee 30", s))

    a, b = asyncio.run(zwei())
    assert route.call_count == 1 and a == b


@respx.mock
def test_overpass_abbruch_mit_status_200_wird_nicht_gecacht(s):
    """P3: Meldet Overpass einen Laufzeitfehler mit HTTP 200, gilt das als Ausfall und landet nicht im Cache."""
    respx.post(dienste.OVERPASS_URL).mock(return_value=httpx.Response(200, json={
        "elements": [], "remark": "runtime error: Query timed out in query at line 1 after 26 seconds."}))
    with pytest.raises(DienstNichtErreichbar):
        asyncio.run(umfeld_pois(51.3116, 9.4881, s))
    assert s.exec(select(GeoCache)).all() == []


@respx.mock
def test_photon_ist_gedrosselt(s):
    """S4: Auch Photon bekommt einen Mindestabstand (0,5 s) zwischen zwei verschiedenen Anfragen."""
    zeiten = []

    def antwort(_request):
        """Merkt sich den Zeitpunkt. Eingabe: Anfrage. Ausgabe: Photon-Antwort."""
        zeiten.append(time.monotonic())
        return httpx.Response(200, json=PHOTON)

    respx.get(dienste.PHOTON_URL).mock(side_effect=antwort)
    asyncio.run(vorschlaege("Lindenallee 3", s))
    asyncio.run(vorschlaege("Lindenallee 30", s))
    assert zeiten[1] - zeiten[0] >= 0.5


@respx.mock
def test_abgelaufene_eintraege_werden_geloescht(s):
    """S6: Beim Schreiben verschwinden Einträge, die älter als 30 Tage sind; der Cache wächst nicht endlos."""
    cache.schreiben(s, "photon", {"q": "alt"}, {"features": []})
    alt = s.exec(select(GeoCache)).one()
    alt.abgerufen_am = dt.datetime.now(dt.UTC) - dt.timedelta(days=31)
    s.add(alt)
    s.commit()
    cache.schreiben(s, "photon", {"q": "neu"}, {"features": []})
    assert [e.anfrage_hash for e in s.exec(select(GeoCache)).all()] == [cache.schluessel({"q": "neu"})]


@respx.mock
def test_unerwartetes_antwortformat_ist_ausfall_und_wird_nicht_gecacht(s):
    """S7: Eine Antwort in fremdem Format wird zu DienstNichtErreichbar (API: 503 statt 500) und nicht gespeichert."""
    respx.get(dienste.PHOTON_URL).mock(return_value=httpx.Response(200, json={"fehler": "anders"}))
    with pytest.raises(DienstNichtErreichbar):
        asyncio.run(vorschlaege("Lindenallee 30", s))
    assert s.exec(select(GeoCache)).all() == []


def test_drossel_gilt_ueber_threads_und_ereignisschleifen():
    """P5: Zwei Threads mit eigener Ereignisschleife teilen sich den Mindestabstand einer Drossel."""
    drossel, zeiten = Drossel(0.3), []

    def lauf():
        """Zwei Wartevorgänge in einer eigenen Ereignisschleife. Ausgabe: keine (Zeitpunkte in zeiten)."""
        async def zweimal():
            """Wartet zweimal auf die Drossel und merkt sich die Zeitpunkte. Ausgabe: keine."""
            for _ in range(2):
                await drossel.warte()
                zeiten.append(time.monotonic())
        asyncio.run(zweimal())

    threads = [threading.Thread(target=lauf) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    zeiten.sort()
    assert min(b - a for a, b in itertools.pairwise(zeiten)) >= 0.29


@respx.mock
def test_wegezeit_nennt_das_abrufdatum(s):
    """P7: Eine Wegezeit aus dem Cache nennt im Rechenweg, wann OSRM sie geliefert hat."""
    respx.post(dienste.OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": [
        {"type": "node", "lat": 51.3130, "lon": 9.4800, "tags": {"highway": "bus_stop", "name": "Lindenplatz"}}]}))
    respx.get(url__startswith=dienste.ROUTING_URL["fuss"]).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, 120.0]], "distances": [[0, 150.0]]}))
    respx.get(url__startswith=dienste.ROUTING_URL["rad"]).mock(return_value=httpx.Response(503))
    asyncio.run(umfeld(51.3116, 9.4881, s))
    vor_zehn_tagen = dt.datetime.now(dt.UTC) - dt.timedelta(days=10)
    for e in s.exec(select(GeoCache)).all():
        e.abgerufen_am = vor_zehn_tagen
        s.add(e)
    s.commit()
    poi = asyncio.run(umfeld(51.3116, 9.4881, s)).pois[0]
    assert f"abgerufen am {vor_zehn_tagen.astimezone():%d.%m.%Y}" in poi.zu_fuss.rechenweg_text
