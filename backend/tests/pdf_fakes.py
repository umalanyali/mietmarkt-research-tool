"""Erzeugt kleine, synthetische PDF-Dateien für Tests (fiktive Musterstadt-Exposés), ohne zusätzliche Bibliothek."""


def pdf(seiten: list[str]) -> bytes:
    """Ein PDF mit einer Textseite je Eintrag (Zeilen per „\\n“), Schrift Helvetica mit WinAnsi-Kodierung (Umlaute).

    Eingabe: Text je Seite. Ausgabe: Inhalt der PDF-Datei.
    """
    objekte = ["<< /Type /Catalog /Pages 2 0 R >>", ""]  # Objekt 2 (Seitenbaum) folgt, wenn die Seiten feststehen
    objekte.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")  # Objekt 3
    seiten_ids = []
    for text in seiten:
        zeilen = [z.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for z in text.split("\n")]
        inhalt = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({z}) Tj T*" for z in zeilen) + " ET"
        daten = inhalt.encode("cp1252")
        objekte.append(f"<< /Length {len(daten)} >>\nstream\n".encode("cp1252") + daten + b"\nendstream")
        objekte.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {len(objekte)} 0 R "
                       "/Resources << /Font << /F1 3 0 R >> >> >>")
        seiten_ids.append(len(objekte))
    objekte[1] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in seiten_ids)}] /Count {len(seiten_ids)} >>"
    aus, positionen = bytearray(b"%PDF-1.4\n"), []
    for nr, obj in enumerate(objekte, 1):
        positionen.append(len(aus))
        aus += f"{nr} 0 obj\n".encode() + (obj if isinstance(obj, bytes) else obj.encode("cp1252")) + b"\nendobj\n"
    xref = len(aus)
    aus += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode()
    aus += b"".join(f"{p:010d} 00000 n \n".encode() for p in positionen)
    aus += f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(aus)
