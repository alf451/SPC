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
ENV_FILE="$PROJECT_ROOT/backend/.env"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Backend non risulta installato. Eseguire prima installer/install.sh" >&2
    exit 1
fi

BACKEND_PORT="$(grep '^BACKEND_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
if grep -q '^BACKEND_SSL_CERTFILE=' "$ENV_FILE" 2>/dev/null; then
    SCHEME="https"
else
    SCHEME="http"
fi

mkdir -p "$LOGS_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Backend già in esecuzione (PID $(cat "$PID_FILE"))"
else
    # "exec" dentro la subshell sostituisce la subshell stessa con nohup/python
    # (stesso PID per tutta la catena): senza "exec", $! dopo "(...) &" darebbe
    # il PID della subshell wrapper, non quello reale del processo, e stop.sh
    # ucciderebbe il processo sbagliato.
    # "run.py" legge BACKEND_HOST/BACKEND_PORT/BACKEND_SSL_* da backend/.env:
    # non serve passarli qui, così questo script non deve conoscere la scelta
    # fatta in fase di installazione.
    (
        cd "$PROJECT_ROOT/backend"
        exec nohup "$VENV_DIR/bin/python" run.py \
            > "$LOGS_DIR/backend.log" 2> "$LOGS_DIR/backend.err.log"
    ) &
    echo $! > "$PID_FILE"
    echo "Backend avviato (PID $(cat "$PID_FILE")), log in $LOGS_DIR/backend.log"
fi

echo -n "Attendo che risponda"
for _ in $(seq 1 20); do
    # -k: accetta anche il certificato auto-firmato (curl non ha il problema
    # di validazione "process-wide" che ha PowerShell 5.1 - qui è solo un flag)
    if curl -fsk -o /dev/null "${SCHEME}://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null; then
        echo " pronto."
        echo ""
        echo "Backend: ${SCHEME}://127.0.0.1:${BACKEND_PORT}/docs"
        exit 0
    fi
    echo -n "."
    sleep 1
done
echo ""
echo "ATTENZIONE: nessuna risposta entro 20s - controllare $LOGS_DIR/backend.err.log" >&2
