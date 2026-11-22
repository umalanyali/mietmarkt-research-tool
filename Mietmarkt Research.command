#!/usr/bin/env bash
# Doppelklick im Finder startet Mietmarkt Research und öffnet den Browser.
# Läuft die App schon, wird nur der Browser geöffnet.
# Beenden: dieses Terminalfenster schließen oder Strg+C drücken.

cd "$(dirname "$0")"
# Finder-Start kennt nicht immer den vollen PATH (Homebrew, Node, uv)
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

URL="http://localhost:5173"

if curl -s -o /dev/null --max-time 2 "$URL"; then
  echo "Mietmarkt Research läuft bereits – öffne $URL"
  open "$URL"
  exit 0
fi

./start.sh
status=$?
if [ $status -ne 0 ]; then
  echo
  echo "Start fehlgeschlagen (Code $status). Fenster bleibt offen – Meldung oben prüfen."
  read -r -p "Enter zum Schließen …"
fi
