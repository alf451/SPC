#!/usr/bin/env bash
# Rimuove il virtualenv Python e ferma il backend. NON tocca il database
# PostgreSQL (potrebbe contenere dati reali importati) né disinstalla i
# pacchetti apt di sistema (postgresql potrebbe servire ad altro) — per
# entrambi stampa il comando da lanciare a mano se davvero li si vuole rimuovere.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime"

echo "Questo rimuove $RUNTIME_DIR (virtualenv, log, segreti) e backend/.env."
echo "Il database PostgreSQL 'leank_spc' NON viene toccato."
read -r -p "Confermi? (scrivi 'si' per procedere) " CONFIRM
if [ "$CONFIRM" != "si" ]; then
    echo "Annullato."
    exit 0
fi

"$(dirname "${BASH_SOURCE[0]}")/stop.sh" || true

rm -rf "$RUNTIME_DIR"
rm -f "$PROJECT_ROOT/backend/.env"

echo ""
echo "Disinstallazione completata."
echo ""
echo "Per eliminare anche il database (irreversibile):"
echo "  sudo -u postgres psql -c \"DROP DATABASE leank_spc;\""
echo "  sudo -u postgres psql -c \"DROP ROLE leank_spc;\""
echo ""
echo "Per rimuovere PostgreSQL dal sistema (solo se non serve ad altro):"
echo "  sudo apt purge postgresql postgresql-contrib && sudo apt autoremove"
