#!/usr/bin/env bash
# Installer per Ubuntu/Debian: usa i pacchetti di sistema (apt) invece del
# trucco "zero admin" di install.ps1 — su Linux un deployment è più
# probabilmente un server permanente, non una convivenza temporanea su un
# PC di produzione altrui, quindi sudo/apt sono normali qui.
# Rieseguibile in sicurezza: salta i passi già completati.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
VENV_DIR="$RUNTIME_DIR/venv"
LOGS_DIR="$RUNTIME_DIR/logs"
SECRETS_DIR="$RUNTIME_DIR/secrets"
PG_DB="leank_spc"
PG_USER="leank_spc"

mkdir -p "$RUNTIME_DIR" "$LOGS_DIR" "$SECRETS_DIR"

random_secret() {
    # $1 = lunghezza. Usa python3 (garantito presente dopo il passo 1) invece
    # di openssl per non aggiungere un'altra dipendenza di sistema.
    python3 -c "import secrets; print(secrets.token_urlsafe($1))"
}

echo "=== leank-spc — installazione Ubuntu/Debian ==="
echo "Cartella progetto: $PROJECT_ROOT"

echo ""
echo ">> Pacchetti di sistema (richiede sudo se mancano)"
MISSING=()
command -v python3 >/dev/null 2>&1 || MISSING+=(python3)
python3 -c "import venv" >/dev/null 2>&1 || MISSING+=(python3-venv)
command -v pip3 >/dev/null 2>&1 || MISSING+=(python3-pip)
command -v psql >/dev/null 2>&1 || MISSING+=(postgresql postgresql-contrib)
command -v curl >/dev/null 2>&1 || MISSING+=(curl)
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "   Installo: ${MISSING[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING[@]}"
else
    echo "   OK: già presenti"
fi
sudo systemctl enable --now postgresql >/dev/null

echo ""
echo ">> Ambiente Python"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "   Creato virtualenv in $VENV_DIR"
else
    echo "   OK: virtualenv già presente"
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -q -r "$PROJECT_ROOT/backend/requirements.txt" -r "$PROJECT_ROOT/edge-agent/requirements.txt"
echo "   OK: dipendenze installate"

echo ""
echo ">> Database applicativo"
APP_PASSWORD_FILE="$SECRETS_DIR/pg_app_password.txt"
[ -f "$APP_PASSWORD_FILE" ] || random_secret 24 > "$APP_PASSWORD_FILE"
APP_PASSWORD="$(cat "$APP_PASSWORD_FILE")"

ROLE_EXISTS="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'")"
if [ "$ROLE_EXISTS" != "1" ]; then
    sudo -u postgres psql -c "CREATE ROLE $PG_USER LOGIN PASSWORD '$APP_PASSWORD';" >/dev/null
fi
DB_EXISTS="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'")"
if [ "$DB_EXISTS" != "1" ]; then
    sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;" >/dev/null
fi
echo "   OK: database '$PG_DB' pronto (utente '$PG_USER')"

echo ""
echo ">> Porta, raggiungibilità in rete e HTTPS"
ENV_FILE="$PROJECT_ROOT/backend/.env"
# Variabili d'ambiente per uso non interattivo/scriptato: PORT, EXPOSE_NETWORK
# (si/no), HTTPS (si/no), SSL_CERT_FILE, SSL_KEY_FILE. Se non impostate e lo
# script gira in un terminale, vengono chieste; altrimenti si usano i default.
if [ -f "$ENV_FILE" ] && grep -q "^BACKEND_PORT=" "$ENV_FILE" && [ -z "${PORT:-}" ] && [ -z "${EXPOSE_NETWORK:-}" ] && [ -z "${HTTPS:-}" ]; then
    BACKEND_PORT="$(grep '^BACKEND_PORT=' "$ENV_FILE" | cut -d= -f2)"
    BACKEND_HOST="$(grep '^BACKEND_HOST=' "$ENV_FILE" | cut -d= -f2)"
    SSL_CERT_PATH="$(grep '^BACKEND_SSL_CERTFILE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)"
    SSL_KEY_PATH="$(grep '^BACKEND_SSL_KEYFILE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)"
    echo "   Configurazione già presente: ${BACKEND_HOST}:${BACKEND_PORT} (invariata)"
else
    if [ -z "${PORT:-}" ] && [ -t 0 ]; then
        read -r -p "Porta del backend [invio per 8000]: " BACKEND_PORT
        BACKEND_PORT="${BACKEND_PORT:-8000}"
    else
        BACKEND_PORT="${PORT:-8000}"
    fi
    if (echo > "/dev/tcp/127.0.0.1/$BACKEND_PORT") 2>/dev/null; then
        echo "   ATTENZIONE: la porta $BACKEND_PORT risulta già in uso da un altro programma - sceglierne un'altra."
    fi

    if [ -z "${EXPOSE_NETWORK:-}" ] && [ -t 0 ]; then
        read -r -p "Raggiungibile anche da altre macchine della rete, non solo da questa? [s/N]: " ans
        EXPOSE_NETWORK="$ans"
    fi
    if [[ "${EXPOSE_NETWORK:-}" =~ ^[sSyY] ]]; then
        BACKEND_HOST="0.0.0.0"
    else
        BACKEND_HOST="127.0.0.1"
    fi
    echo "   Backend su ${BACKEND_HOST}:${BACKEND_PORT}"

    if [ "$BACKEND_HOST" = "0.0.0.0" ] && command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
        sudo ufw allow "${BACKEND_PORT}/tcp" >/dev/null
        echo "   OK: porta $BACKEND_PORT aperta su ufw"
    fi

    if [ -z "${HTTPS:-}" ] && [ -t 0 ]; then
        read -r -p "Usare HTTPS invece di HTTP? [s/N]: " ans
        HTTPS="$ans"
    fi
    SSL_CERT_PATH=""
    SSL_KEY_PATH=""
    if [[ "${HTTPS:-}" =~ ^[sSyY] ]] || [ -n "${SSL_CERT_FILE:-}" ]; then
        SSL_CERT_PATH="$SECRETS_DIR/backend_cert.pem"
        SSL_KEY_PATH="$SECRETS_DIR/backend_key.pem"
        if [ -n "${SSL_CERT_FILE:-}" ]; then
            cp "$SSL_CERT_FILE" "$SSL_CERT_PATH"
            cp "$SSL_KEY_FILE" "$SSL_KEY_PATH"
            echo "   OK: certificato fornito copiato in $SECRETS_DIR"
        else
            echo "   Generazione certificato auto-firmato (per LAN - non per esposizione pubblica)"
            HOSTNAME_VAL="$(hostname)"
            IPS="$(hostname -I 2>/dev/null || true)"
            (cd "$PROJECT_ROOT/backend" && "$VENV_DIR/bin/python" generate_cert.py "$SSL_CERT_PATH" "$SSL_KEY_PATH" "$HOSTNAME_VAL" $IPS)
        fi
    fi
fi

echo ""
echo ">> Configurazione backend"
JWT_SECRET_FILE="$SECRETS_DIR/jwt_secret.txt"
[ -f "$JWT_SECRET_FILE" ] || random_secret 48 > "$JWT_SECRET_FILE"
JWT_SECRET="$(cat "$JWT_SECRET_FILE")"

SCHEME="http"
SSL_ENV_LINES=""
if [ -n "$SSL_CERT_PATH" ]; then
    SCHEME="https"
    SSL_ENV_LINES=$'BACKEND_SSL_CERTFILE='"$SSL_CERT_PATH"$'\nBACKEND_SSL_KEYFILE='"$SSL_KEY_PATH"
fi

cat > "$PROJECT_ROOT/backend/.env" <<EOF
DATABASE_URL=postgresql+asyncpg://${PG_USER}:${APP_PASSWORD}@127.0.0.1:5432/${PG_DB}
BACKEND_HOST=${BACKEND_HOST}
BACKEND_PORT=${BACKEND_PORT}
${SSL_ENV_LINES}
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:${BACKEND_PORT},https://127.0.0.1:${BACKEND_PORT},null
EOF
echo "   Scritto backend/.env"

echo ""
echo ">> Migration database (alembic upgrade head)"
(cd "$PROJECT_ROOT/backend" && "$VENV_DIR/bin/python" -m alembic upgrade head)
echo "   OK: schema applicato"

echo ""
echo ">> Utente amministratore"
ADMIN_PASSWORD_FILE="$SECRETS_DIR/admin_password.txt"
[ -f "$ADMIN_PASSWORD_FILE" ] || random_secret 12 > "$ADMIN_PASSWORD_FILE"
ADMIN_PASSWORD="$(cat "$ADMIN_PASSWORD_FILE")"
(cd "$PROJECT_ROOT/backend" && "$VENV_DIR/bin/python" create_admin.py admin "$ADMIN_PASSWORD")
echo "   OK: utente 'admin' pronto (password in $ADMIN_PASSWORD_FILE)"

echo ""
echo "=== Installazione completata ==="
echo "Per avviare il backend:  installer/start.sh"
echo "Per fermarlo:            installer/stop.sh"
echo "Per disinstallare:       installer/uninstall.sh"
echo ""
echo "Login iniziale: utente 'admin', password in $ADMIN_PASSWORD_FILE"
echo "Per farlo partire da solo al boot (deployment permanente): vedi installer/leank-spc.service"
echo ""
if [ -n "$SSL_CERT_PATH" ]; then
    echo "HTTPS attivo con certificato auto-firmato: il browser mostrerà un avviso 'connessione non sicura' - è atteso, il traffico è comunque cifrato."
fi
if [ "$BACKEND_HOST" = "0.0.0.0" ]; then
    echo "Backend raggiungibile da questa macchina su:  ${SCHEME}://127.0.0.1:${BACKEND_PORT}/docs"
    echo "Backend raggiungibile da altre postazioni su: ${SCHEME}://$(hostname):${BACKEND_PORT}/docs (o via IP: $(hostname -I 2>/dev/null))"
else
    echo "Backend: ${SCHEME}://127.0.0.1:${BACKEND_PORT}/docs (solo da questa macchina)"
fi
