"""Server-Log in daten/logs/backend.log: Fehler und Zugriffe landen in der Datei, ein API-Schlüssel nie."""
import logging

from api.main import protokoll_einrichten


def test_log_datei_mit_fehlern_ohne_schluessel(tmp_path):
    """Ausnahmen samt Traceback und uvicorn-Zugriffe stehen in der Datei; „sk-ant-…“ wird unkenntlich gemacht,
    auch im Traceback."""
    datei = tmp_path / "logs" / "backend.log"
    handler = protokoll_einrichten(datei)
    try:
        try:
            raise ValueError("Schlüssel sk-ant-api03-GEHEIM_123 abgelehnt")
        except ValueError:
            logging.getLogger("mietmarkt.laeufe").exception("Lauf %s unterbrochen", "abc")
        logging.getLogger("uvicorn.access").info('"GET /api/projekte HTTP/1.1" 500')
    finally:
        for name in ("", "uvicorn", "uvicorn.access"):
            logging.getLogger(name).removeHandler(handler)
        handler.close()
    text = datei.read_text(encoding="utf-8")
    assert "Lauf abc unterbrochen" in text and "Traceback" in text and "GET /api/projekte HTTP/1.1\" 500" in text
    assert "GEHEIM" not in text and "sk-ant-***" in text
