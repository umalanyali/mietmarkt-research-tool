"""Export des geprüften Berichts als Markdown und PowerPoint (python-pptx): warme Neutraltöne, ohne Logo.
Der Bericht kommt fertig gefüllt aus agenten/bericht.py; hier wird nur gesetzt, nicht gerechnet."""
import io
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .modelle import Projekt

ABSCHNITTE = {"lage": "Lage", "markt": "Markt", "mietansatz": "Mietansatz", "risiken": "Risiken"}
# Farben wie im Frontend (index.css): Sand-Hintergrund, Stein-Text, Oliv als Akzent
SAND, TEXT, LEISE, OLIV = (RGBColor.from_string(x) for x in ("F3F1EC", "1A1A19", "6B6862", "56602F"))


def _kopf(p: Projekt) -> str:
    """Untertitel mit Adresse und Stichtag. Eingabe: Projekt. Ausgabe: Text."""
    return f"{p.adresse}, {p.plz} {p.ort} · Stichtag {p.stichtag:%d.%m.%Y}"


# Nur was in Markdown wirkt, wird maskiert: Bild- und Linkbeginn „![“, Link-, Referenzklammer und Linkdefinition
# „](“, „][“ bzw. „]:“, HTML-Tags und Autolinks „<x…“ sowie Code-Backticks. Gewöhnliche Klammern bleiben lesbar.
WIRKSAM = re.compile(r"!(?=\[)|\[(?=[^\]]*\]\s*[(\[:])|\](?=\s*[(\[:])|<(?=[A-Za-z/!?])|`")
# Nackte URLs und E-Mail-Adressen macht GFM klickbar; entschärft („https[:]//“, „www[.]“, „mailto[:]“, „a[@]b.de“)
# bleiben sie lesbar, aber kein Link. Ersetzt wird immer das letzte Zeichen des Treffers.
URL = re.compile(r"(?i)\b\w+:(?=//)|\bwww\.|\bmailto:|(?<=\w)@(?=[\w-]+\.)")


def _md(text: str) -> str:
    """Text aus Modell, Import oder Projektdaten für Markdown maskieren; die eigenen Fußnotenzeichen [^n] bleiben.

    Eingabe: Text. Ausgabe: Text, in dem kein Link, Bild oder HTML wirkt. Warum: Ein eingeschleuster Text (OSM-Name,
    Importfeld) könnte sonst im Markdown-Viewer ein Bild von fremder Adresse laden oder einen Link unterschieben.
    Zeilenumbrüche werden zu Leerzeichen, damit kein Satz eine Überschrift, Liste oder Linkdefinition beginnt.
    """
    teile = re.split(r"(\[\^\d+\])", " ".join(text.splitlines()))  # ungerade Stellen: eigene Fußnotenzeichen
    def maskieren(t: str) -> str:
        """Maskiert ein Textstück. Eingabe: Text ohne eigene Fußnotenzeichen. Ausgabe: maskierter Text."""
        t = WIRKSAM.sub(lambda m: "\\" + m.group(0), t)
        return URL.sub(lambda m: f"{m[0][:-1]}[{m[0][-1]}]", t)  # nach WIRKSAM, damit „[:]“ so bleibt

    return "".join(t if i % 2 else maskieren(t) for i, t in enumerate(teile))


def _hinweise(b: dict) -> str:
    """Erklärt Markierungen des Berichts. Eingabe: Bericht. Ausgabe: Absatz oder leerer Text (P17)."""
    grund = [m["grund"] for m in b.get("markierungen", [])]
    teile = []
    if n := sum(g != "Aussage ohne Beleg entfernt" for g in grund):
        teile.append(f"[?] steht für eine Zahl ohne Herkunft, die Python entfernt hat ({n}-mal).")
    if n := grund.count("Aussage ohne Beleg entfernt"):
        teile.append(f"{n} Aussage{'n' if n > 1 else ''} ohne Beleg gestrichen.")
    return " ".join(teile)


def markdown(p: Projekt, b: dict) -> str:
    """Bericht als Markdown mit Fußnoten ([^n]). Eingabe: Projekt, gefüllter Bericht. Ausgabe: Text."""
    teile = [f"# Mietmarktbericht: {_md(p.name)}", _md(_kopf(p))]
    teile += [f"## {titel}\n\n{_md(b['abschnitte'].get(k, ''))}" for k, titel in ABSCHNITTE.items()]
    teile.append("## Herkunft der Zahlen\n\n" + "\n".join(f"[^{f['nr']}]: {f['herkunft']} – {_md(f['verweis'])}"
                                                         for f in b["fussnoten"]))
    if hinweis := _hinweise(b):
        teile.append(hinweis)  # eigener Text, nicht maskieren
    if b.get("methoden"):
        teile.append("### Methoden\n\n" + "\n".join(f"- [{m['nr']}] {_md(m['text'])}" for m in b["methoden"]))
    return "\n\n".join(teile) + "\n"


def pptx(p: Projekt, b: dict) -> bytes:
    """Bericht als PowerPoint (16:9): Titelfolie, je Abschnitt eine Folie, Herkunftsfolie.

    Eingabe: Projekt, gefüllter Bericht. Ausgabe: Inhalt der .pptx-Datei. Fußnotenzeichen [^n] werden zu „ [n]“.
    """
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    def folie(titel: str, text: str, groesse: int = 18) -> None:
        """Eine Folie mit Titel, Oliv-Linie und Fließtext. Eingabe: Titel, Text, Schriftgröße. Ausgabe: keine."""
        f = prs.slides.add_slide(prs.slide_layouts[6])  # Layout 6: leer, ohne Platzhalter der Vorlage
        f.background.fill.solid()
        f.background.fill.fore_color.rgb = SAND
        for y, h, inhalt, pt, farbe in ((0.6, 0.9, titel, 32, TEXT), (1.8, 5.2, text, groesse, LEISE)):
            box = f.shapes.add_textbox(Inches(0.8), Inches(y), Inches(11.7), Inches(h)).text_frame
            box.word_wrap = True
            for i, zeile in enumerate(inhalt.split("\n")):
                absatz = box.paragraphs[0] if i == 0 else box.add_paragraph()
                absatz.text = zeile
                absatz.font.size, absatz.font.color.rgb = Pt(pt), farbe
        linie = f.shapes.add_shape(1, Inches(0.8), Inches(1.55), Inches(1.2), Inches(0.05))  # 1 = Rechteck
        linie.fill.solid()
        linie.fill.fore_color.rgb = OLIV
        linie.line.fill.background()

    folie(f"Mietmarktbericht: {p.name}", _kopf(p), 20)
    for k, titel in ABSCHNITTE.items():
        folie(titel, re.sub(r"\[\^(\d+)\]", r" [\1]", b["abschnitte"].get(k, "")))
    folie("Herkunft der Zahlen", "\n".join([f"[{f['nr']}] {f['herkunft']} – {f['verweis']}" for f in b["fussnoten"]]
                                           + [f"[{m['nr']}] {m['text']}" for m in b.get("methoden", [])]
                                           + ([_hinweise(b)] if _hinweise(b) else [])), 11)
    puffer = io.BytesIO()
    prs.save(puffer)
    return puffer.getvalue()
