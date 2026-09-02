#!/usr/bin/env bash
# safir_monitoring kurulum scripti
# Kullanim: sudo bash install.sh [OPTIONS]
#
#   --db-host       MySQL host (varsayilan: localhost)
#   --db-pass       MySQL safir_monitoring kullanici sifresi (varsayilan: admin)
#   --bind-host     API dinleme adresi (varsayilan: 0.0.0.0)
#   --bind-port     API portu (varsayilan: 9768)
#   --keystone-url  Keystone auth URL (varsayilan: http://localhost/identity)
#   --thanos-url    Thanos querier URL (varsayilan: http://localhost:10903)
#   --skip-db       Veritabani olusturmayi atla
#   --skip-keystone Keystone entegrasyonunu atla

set -euo pipefail

# ============================================================================
# Varsayilan degerler
# ============================================================================
DB_HOST="localhost"
DB_PASS="admin"
BIND_HOST="0.0.0.0"
BIND_PORT="9768"
KEYSTONE_URL="http://localhost/identity"
THANOS_URL="http://localhost:10903"
SKIP_DB=false
SKIP_KEYSTONE=false

SERVICE_NAME="safir_monitoring"
INSTALL_DIR="/opt/${SERVICE_NAME}"
VENV_DIR="${INSTALL_DIR}/venv"
CONF_DIR="/etc/${SERVICE_NAME}"
LOG_DIR="/var/log/${SERVICE_NAME}"
RULES_DIR="/var/lib/thanos/rules"

# ============================================================================
# Parametre okuma
# ============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --db-host)      DB_HOST="$2";       shift 2 ;;
        --db-pass)      DB_PASS="$2";       shift 2 ;;
        --bind-host)    BIND_HOST="$2";     shift 2 ;;
        --bind-port)    BIND_PORT="$2";     shift 2 ;;
        --keystone-url) KEYSTONE_URL="$2";  shift 2 ;;
        --thanos-url)   THANOS_URL="$2";    shift 2 ;;
        --skip-db)      SKIP_DB=true;       shift   ;;
        --skip-keystone) SKIP_KEYSTONE=true; shift  ;;
        *) echo "Bilinmeyen parametre: $1"; exit 1  ;;
    esac
done

# ============================================================================
# Root kontrolu
# ============================================================================
if [[ $EUID -ne 0 ]]; then
    echo "HATA: Bu script root olarak calistirilmalidir (sudo bash install.sh)"
    exit 1
fi

echo "============================================"
echo " safir_monitoring Kurulum Scripti"
echo "============================================"
echo ""
echo "  Bind:       ${BIND_HOST}:${BIND_PORT}"
echo "  DB Host:    ${DB_HOST}"
echo "  Keystone:   ${KEYSTONE_URL}"
echo "  Thanos:     ${THANOS_URL}"
echo "  Venv:       ${VENV_DIR}"
echo ""

# ============================================================================
# 1. Dizinler
# ============================================================================
echo "[1/7] Dizinler olusturuluyor..."
mkdir -p "${CONF_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${RULES_DIR}"
mkdir -p "${INSTALL_DIR}"

echo "  -> ${CONF_DIR}"
echo "  -> ${LOG_DIR}"
echo "  -> ${RULES_DIR}"
echo "  -> ${INSTALL_DIR}"

# ============================================================================
# 2. Virtual environment ve Python paketi kurulumu
# ============================================================================
echo "[2/7] Virtual environment olusturuluyor ve paketler kuruluyor..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# venv olustur (varsa yeniden olusturma)
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    echo "  -> venv olusturuldu: ${VENV_DIR}"
else
    echo "  -> venv zaten mevcut: ${VENV_DIR}"
fi

# venv icindeki pip'i guncelle
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel 2>&1 | tail -1

# Paketi ve bagimliliklari venv'e kur
"${VENV_DIR}/bin/pip" install "${SCRIPT_DIR}" 2>&1 | tail -1
"${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" 2>&1 | tail -1

# keystonemiddleware ASGI destegi
"${VENV_DIR}/bin/pip" install git+https://hasan.acar@bitbucket.bilgem.tubitak.gov.tr/scm/~hasan.acar/keystonemiddleware.git 2>&1 | tail -1 || \
    echo "  UYARI: Ozel keystonemiddleware yuklenemedi, mevcut surumu kullaniliyor"

echo "  -> Paket kurulumu tamamlandi"

# ============================================================================
# 3. Konfigrasyon dosyalari
# ============================================================================
echo "[3/7] Konfigurasyon dosyalari olusturuluyor..."

# safir_monitoring.conf
cat > "${CONF_DIR}/${SERVICE_NAME}.conf" << CONFEOF
[DEFAULT]
debug = False
log_name = ${SERVICE_NAME}
log_file = ${LOG_DIR}/${SERVICE_NAME}.log

[keystone_authtoken]
auth_url = ${KEYSTONE_URL}
auth_type = password
username = ${SERVICE_NAME}
user_domain_id = default
password = SAFIR_MONITORING_PASS
project_name = admin
project_domain_id = default
interface = public
region_name = RegionOne
www_authenticate_uri = ${KEYSTONE_URL}
service_token_roles_required = True
service_token_roles = admin

[api_server]
host = ${BIND_HOST}
port = ${BIND_PORT}

[database]
connection = mysql+pymysql://${SERVICE_NAME}:${DB_PASS}@${DB_HOST}:3306/${SERVICE_NAME}?charset=utf8
db_debug = False

[opensearch]
url = https://localhost:9200
username = safircloudwatcher
password = OPENSEARCH_PASS

[email_notifier]
smtp_from = safir@example.com
smtp_host = localhost:587
smtp_user = safir
smtp_pass = SMTP_PASS

[thanos]
querier_endpoint = ${THANOS_URL}
rules_dir = ${RULES_DIR}
CONFEOF

# gunicorn.py
cat > "${CONF_DIR}/gunicorn.py" << 'GUNICORNEOF'
bind = "BIND_HOST:BIND_PORT"
workers = 5
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
reuse_port = True
proc_name = "safir_monitoring"

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["error_file"],
            "propagate": 0,
            "qualname": "gunicorn_error",
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": 0,
            "qualname": "access",
        },
    },
    "handlers": {
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "generic",
            "filename": "/var/log/safir_monitoring/safir_monitoring-error.log",
            "maxBytes": 52428800,
            "backupCount": 5,
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "generic",
            "filename": "/var/log/safir_monitoring/safir_monitoring-access.log",
            "maxBytes": 52428800,
            "backupCount": 5,
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "generic",
        },
    },
    "formatters": {
        "generic": {
            "format": "%(asctime)s.%(msecs)03d %(process)d %(levelname)s [-] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter",
        }
    },
}
GUNICORNEOF

# gunicorn.py icindeki placeholder'lari degistir
sed -i "s/BIND_HOST:BIND_PORT/${BIND_HOST}:${BIND_PORT}/g" "${CONF_DIR}/gunicorn.py"

# api_paste.ini
cat > "${CONF_DIR}/api_paste.ini" << 'PASTEEOF'
[pipeline:main]
pipeline = authtoken safir_monitoring

[app:safir_monitoring]
paste.app_factory = safir_monitoring.main:app_factory

[filter:authtoken]
acl_public_routes = /, /v1, /docs, /api/v1/openapi.json, /api/v1/alerts/webhook, /healthcheck
paste.filter_factory = safir_monitoring.api.middleware:AuthTokenMiddleware.factory
oslo_config_config = None
oslo_config_project = None
oslo_config_file = None
PASTEEOF

echo "  -> ${CONF_DIR}/${SERVICE_NAME}.conf"
echo "  -> ${CONF_DIR}/gunicorn.py"
echo "  -> ${CONF_DIR}/api_paste.ini"

# ============================================================================
# 4. Systemd servisi
# ============================================================================
echo "[4/7] Systemd servisi kuruluyor..."

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SERVICEEOF
[Unit]
Description=Safir Monitoring API Service
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=notify
WorkingDirectory=${INSTALL_DIR}

Environment="oslo_config_file=${CONF_DIR}/${SERVICE_NAME}.conf"
Environment="config_base_path=${CONF_DIR}/"
Environment="PATH=${VENV_DIR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="VIRTUAL_ENV=${VENV_DIR}"

ExecStart=${VENV_DIR}/bin/gunicorn \\
    -c ${CONF_DIR}/gunicorn.py \\
    safir_monitoring.main:asgi_app\\(\\'\\) \\
    --env oslo_config_file=${CONF_DIR}/${SERVICE_NAME}.conf \\
    --env config_base_path=${CONF_DIR}/

ExecReload=/usr/bin/kill -HUP \$MAINPID

Restart=on-failure
RestartSec=5
TimeoutStopSec=300
KillMode=process

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
echo "  -> ${SERVICE_NAME}.service kuruldu"

# ============================================================================
# 5. Veritabani
# ============================================================================
if [[ "${SKIP_DB}" == false ]]; then
    echo "[5/7] Veritabani olusturuluyor..."
    mysql -uroot -e "
        CREATE DATABASE IF NOT EXISTS ${SERVICE_NAME};
        CREATE USER IF NOT EXISTS '${SERVICE_NAME}'@'localhost' IDENTIFIED BY '${DB_PASS}';
        CREATE USER IF NOT EXISTS '${SERVICE_NAME}'@'%' IDENTIFIED BY '${DB_PASS}';
        GRANT ALL PRIVILEGES ON ${SERVICE_NAME}.* TO '${SERVICE_NAME}'@'localhost';
        GRANT ALL PRIVILEGES ON ${SERVICE_NAME}.* TO '${SERVICE_NAME}'@'%';
        FLUSH PRIVILEGES;
    " 2>/dev/null && echo "  -> Veritabani ve kullanici olusturuldu" || \
        echo "  UYARI: MySQL'e root olarak baglanilamadi. Veritabanini manuel olusturun."

    echo "  Alembic migration calistiriliyor..."
    cd "${SCRIPT_DIR}/safir_monitoring/db"
    "${VENV_DIR}/bin/alembic" upgrade head 2>&1 | tail -1 || echo "  UYARI: Alembic migration basarisiz"
    cd "${SCRIPT_DIR}"
else
    echo "[5/7] Veritabani adimlari atlandi (--skip-db)"
fi

# ============================================================================
# 6. Keystone entegrasyonu
# ============================================================================
if [[ "${SKIP_KEYSTONE}" == false ]]; then
    echo "[6/7] Keystone entegrasyonu..."
    echo "  Asagidaki komutlari OpenStack admin olarak calistirin:"
    echo ""
    echo "    openstack user create ${SERVICE_NAME} --password SAFIR_MONITORING_PASS"
    echo "    openstack role add --project service --user ${SERVICE_NAME} admin"
    echo "    openstack service create monitoring --name ${SERVICE_NAME} --description 'Safir Monitoring Service'"
    echo "    openstack endpoint create ${SERVICE_NAME} --region RegionOne public http://CONTROLLER_HOST:${BIND_PORT}"
    echo "    openstack endpoint create ${SERVICE_NAME} --region RegionOne admin http://CONTROLLER_HOST:${BIND_PORT}"
    echo "    openstack endpoint create ${SERVICE_NAME} --region RegionOne internal http://CONTROLLER_HOST:${BIND_PORT}"
    echo ""
else
    echo "[6/7] Keystone adimlari atlandi (--skip-keystone)"
fi

# ============================================================================
# 7. Sonuc
# ============================================================================
echo "[7/7] Kurulum tamamlandi!"
echo ""
echo "============================================"
echo " Sonraki Adimlar"
echo "============================================"
echo ""
echo "  1. Konfigurasyon dosyasini duzenleyin:"
echo "     vi ${CONF_DIR}/${SERVICE_NAME}.conf"
echo ""
echo "  2. Ozellikle su alanlari guncelleyin:"
echo "     - [keystone_authtoken] password"
echo "     - [database] connection"
echo "     - [opensearch] url, username, password"
echo "     - [email_notifier] smtp_*"
echo "     - [thanos] querier_endpoint"
echo ""
echo "  3. Servisi baslatin:"
echo "     sudo systemctl enable ${SERVICE_NAME}"
echo "     sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "  4. Durumu kontrol edin:"
echo "     sudo systemctl status ${SERVICE_NAME}"
echo "     curl http://localhost:${BIND_PORT}/api/v1/openapi.json"
echo ""
echo "  5. Loglar:"
echo "     tail -f ${LOG_DIR}/${SERVICE_NAME}.log"
echo "     tail -f ${LOG_DIR}/${SERVICE_NAME}-error.log"
echo ""
echo "  Venv aktiflestirilmesi (manuel islemler icin):"
echo "     source ${VENV_DIR}/bin/activate"
echo ""
