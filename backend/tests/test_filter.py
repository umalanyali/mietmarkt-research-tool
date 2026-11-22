"""Filter von Comps nach Radius, Baujahr und Typ, jeweils mit Rechenweg."""
from conftest import comp

from mietmarkt.comps import filtern


def test_radius_schliesst_entfernte_comps_aus():
    """Ein Comp 3 km nördlich fällt bei Radius 2 km heraus."""
    nah = comp(1)
    fern = comp(2, lat=51.3127 + 3 / 111.19)
    a = filtern([nah, fern], zentrum=(51.3127, 9.4797), radius_km=2)
    assert [c.nr for c in a.comps] == [1]
    assert "Nr. 2" in a.rechenweg_text


def test_baujahr_und_typ_kombiniert():
    """Baujahr ab 2025 und nur DG: beide Bedingungen gelten zugleich."""
    cs = [comp(1, typ="DG", baujahr=2025), comp(2, typ="Regel", baujahr=2026), comp(3, typ="DG", baujahr=2020)]
    a = filtern(cs, baujahr_ab=2025, typen={"DG"})
    assert [c.nr for c in a.comps] == [1]


def test_ohne_kriterien_bleibt_alles():
    """Ohne Filter bleiben alle Comps, der Rechenweg sagt das."""
    a = filtern([comp(1), comp(2)])
    assert len(a.comps) == 2 and "ohne Filter" in a.rechenweg_text


def test_fehlendes_baujahr_faellt_bei_baujahrfilter_raus():
    """Ein Comp ohne Baujahr kann die Bedingung nicht erfüllen und wird ausgeschlossen."""
    a = filtern([comp(1, baujahr=None)], baujahr_ab=2020)
    assert a.comps == []
