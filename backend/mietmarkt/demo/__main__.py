"""Kommandozeile für den Demo-Datensatz: python -m mietmarkt.demo seed [--db PFAD]."""
import argparse
from pathlib import Path

from ..db import datenbankpfad, engine
from . import seed

parser = argparse.ArgumentParser(prog="python -m mietmarkt.demo", description="Synthetischen Musterstadt-Datensatz laden")
parser.add_argument("befehl", choices=["seed"], help="seed: Datenbank leeren und Demo-Daten laden")
parser.add_argument("--db", type=Path, default=None, help="Pfad der SQLite-Datei (Standard: daten/mietmarkt.db)")
argumente = parser.parse_args()

pfad = argumente.db or datenbankpfad()
anzahl = seed(engine(pfad))
print(f"Demo-Datensatz geladen: {anzahl} Projekte in {pfad}")
