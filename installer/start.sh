#!/usr/bin/env bash
# Avvia il backend leank-spc. PostgreSQL è gestito da systemd (avviato da
# install.sh con "systemctl enable --now") e non ha bisogno di essere
# riavviato qui.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
VENV_DIR="$RUNTIME_DIR/venv"
LOGS_DIR="$RUNTIME_DIR/logs"
PID_FILE="$RUNTIME_DIR/backend.pid"

if [ ! -x "$VENV_DIR/bin/uvicorn" ]; then
    echo "Backend non risulta installato. Eseguire prima installer/install.sh" >&2
    exit 1
fi

mkdir -p "$LOGS_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Backend già in esecuzione (PID $(cat "$PID_FILE"))"
else
    # "exec" dentro la subshell sostituisce la subshell stessa con nohup/uvicorn
    # (stesso PID per tutta la catena): senza "exec", $! dopo "(...) &" darebbe
    # il PID della subshell wrapper, non quello reale di uvicorn, e stop.sh
    # ucciderebbe il processo sbagliato.
    (
        cd "$PROJECT_ROOT/backend"
        exec nohup "$VENV_DIR/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 \
            > "$LOGS_DIR/backend.log" 2> "$LOGS_DIR/backend.err.log"
    ) &
    echo $! > "$PID_FILE"
    echo "Backend avviato (PID $(cat "$PID_FILE")), log in $LOGS_DIR/backend.log"
fi

echo -n "Attendo che risponda"
for _ in $(seq 1 20); do
    if curl -fs -o /dev/null "http://127.0.0.1:8000/health" 2>/dev/null; then
        echo " pronto."
        echo ""
        echo "Backend: http://127.0.0.1:8000/docs"
        exit 0
    fi
    echo -n "."
    sleep 1
done
echo ""
echo "ATTENZIONE: nessuna risposta entro 20s - controllare $LOGS_DIR/backend.err.log" >&2
