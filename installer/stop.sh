#!/usr/bin/env bash
# Ferma il backend leank-spc. PostgreSQL resta attivo (gestito da systemd) —
# non è compito di questo script, che tocca solo ciò che ha avviato lui.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/runtime/backend.pid"

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Backend fermato (PID $PID)"
    else
        echo "Non risultava attivo"
    fi
    rm -f "$PID_FILE"
else
    echo "Nessun processo da fermare"
fi

echo "Nota: PostgreSQL resta attivo (systemd) - 'sudo systemctl stop postgresql' per fermarlo."
