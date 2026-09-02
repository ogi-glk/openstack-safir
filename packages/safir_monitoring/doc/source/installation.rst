##############################################
Safir Monitoring Kurulum ve Konfigurasyon
##############################################

Genel Bakis
============

safir_monitoring, OpenStack bulut ortamlari icin metrik toplama, alarm yonetimi
ve kaynak izleme hizmeti sunan bir FastAPI tabanli REST API servisidir.

**Bagimliliklar:**

- Python 3.10+
- MySQL/MariaDB 8.0+
- Thanos Querier (Prometheus uyumlu)
- OpenStack Keystone (kimlik dogrulama)
- OpenSearch (alarm gecmisi)

**Varsayilan port:** ``9768``

**Kurulum dizini:** ``/opt/safir_monitoring``

**Virtual environment:** ``/opt/safir_monitoring/venv``

Otomatik Kurulum
=================

Projedeki ``install.sh`` scripti tum kurulum adimlarini otomatik gerceklestirir.
Tum Python paketleri izole bir virtual environment icine kurulur.

Temel kullanim::

    sudo bash install.sh

Parametreli kullanim::

    sudo bash install.sh \
        --bind-host 10.8.132.48 \
        --bind-port 9768 \
        --db-host 10.13.0.10 \
        --db-pass guclu_sifre \
        --keystone-url http://10.13.0.10:5000/v3 \
        --thanos-url http://10.13.0.10:10903

Kullanilabilir parametreler:

========================  ============================  =========================
Parametre                 Aciklama                      Varsayilan
========================  ============================  =========================
``--bind-host``           API dinleme adresi            ``0.0.0.0``
``--bind-port``           API portu                     ``9768``
``--db-host``             MySQL sunucu adresi           ``localhost``
``--db-pass``             MySQL kullanici sifresi       ``admin``
``--keystone-url``        Keystone auth URL             ``http://localhost/identity``
``--thanos-url``          Thanos querier URL            ``http://localhost:10903``
``--skip-db``             Veritabani adimlarini atla    -
``--skip-keystone``       Keystone adimlarini atla      -
========================  ============================  =========================

Script asagidaki islemleri yapar:

1. Gerekli dizinleri olusturur (``/opt/safir_monitoring``, ``/etc/safir_monitoring``, ``/var/log/safir_monitoring``, ``/var/lib/thanos/rules``)
2. ``/opt/safir_monitoring/venv`` altinda Python virtual environment olusturur
3. Paketi ve bagimliliklari venv icine kurar
4. Konfigurasyon dosyalarini olusturur
5. Systemd servisini kaydeder (root olarak calisir, venv icindeki gunicorn'u kullanir)
6. Veritabanini ve kullaniciyi olusturur, Alembic migration calistirir
7. Keystone entegrasyon komutlarini gosterir

Manuel Kurulum
===============

Asagidaki adimlar ``install.sh`` scriptinin yaptigi islemleri manuel olarak aciklar.

1. Kaynak Koddan Kurulum
-------------------------

Repoyu klonlayin::

    git clone <repo-url> safir_monitoring
    cd safir_monitoring

Kurulum dizinini ve virtual environment'i olusturun::

    sudo mkdir -p /opt/safir_monitoring
    sudo python3 -m venv /opt/safir_monitoring/venv

venv'i aktive edip paketleri kurun::

    source /opt/safir_monitoring/venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install .
    pip install -r requirements.txt

Ozel keystonemiddleware (ASGI destekli) surumunu kurun::

    pip install git+https://hasan.acar@bitbucket.bilgem.tubitak.gov.tr/scm/~hasan.acar/keystonemiddleware.git

.. note::

   Bundan sonraki tum ``pip`` ve ``alembic`` komutlari venv aktifken
   calistirilmalidir. Alternatif olarak tam yol kullanilabilir:
   ``/opt/safir_monitoring/venv/bin/pip``

2. Dizinler
----------------------------------

Gerekli dizinleri olusturun::

    sudo mkdir -p /etc/safir_monitoring
    sudo mkdir -p /var/log/safir_monitoring
    sudo mkdir -p /var/lib/thanos/rules

3. Konfigurasyon Dosyalari
---------------------------

Ornek dosyalari kopyalayin::

    sudo cp etc/safir_monitoring/safir_monitoring.conf /etc/safir_monitoring/
    sudo cp etc/safir_monitoring/api_paste.ini /etc/safir_monitoring/
    sudo cp etc/safir_monitoring/gunicorn.py /etc/safir_monitoring/

``/etc/safir_monitoring/safir_monitoring.conf`` dosyasini duzenleyin:

.. code-block:: ini

    [DEFAULT]
    debug = False
    log_name = safir_monitoring
    log_file = /var/log/safir_monitoring/safir_monitoring.log

    [keystone_authtoken]
    auth_url = http://CONTROLLER_HOST/identity
    auth_type = password
    username = safir_monitoring
    user_domain_id = default
    password = SAFIR_MONITORING_PASS
    project_name = admin
    project_domain_id = default
    interface = public
    region_name = RegionOne
    www_authenticate_uri = http://CONTROLLER_HOST/identity
    service_token_roles_required = True
    service_token_roles = admin

    [api_server]
    host = 0.0.0.0
    port = 9768

    [database]
    connection = mysql+pymysql://safir_monitoring:DB_PASS@DB_HOST:3306/safir_monitoring?charset=utf8
    db_debug = False

    [opensearch]
    url = https://OPENSEARCH_HOST:9200
    username = safircloudwatcher
    password = OPENSEARCH_PASS

    [email_notifier]
    smtp_from = safir@example.com
    smtp_host = MTA_HOST:587
    smtp_user = safir_user
    smtp_pass = SMTP_PASS

    [thanos]
    querier_endpoint = http://THANOS_HOST:10903
    rules_dir = /var/lib/thanos/rules

``/etc/safir_monitoring/gunicorn.py`` dosyasinda ``bind`` adresini guncelleyin:

.. code-block:: python

    bind = "0.0.0.0:9768"

4. Veritabani Kurulumu
-----------------------

MySQL'de veritabani ve kullanici olusturun::

    mysql -uroot -p <<EOF
    CREATE DATABASE IF NOT EXISTS safir_monitoring;
    CREATE USER IF NOT EXISTS 'safir_monitoring'@'localhost' IDENTIFIED BY 'DB_PASS';
    CREATE USER IF NOT EXISTS 'safir_monitoring'@'%' IDENTIFIED BY 'DB_PASS';
    GRANT ALL PRIVILEGES ON safir_monitoring.* TO 'safir_monitoring'@'localhost';
    GRANT ALL PRIVILEGES ON safir_monitoring.* TO 'safir_monitoring'@'%';
    FLUSH PRIVILEGES;
    EOF

Alembic migration'larini calistirin (venv aktif olmali)::

    source /opt/safir_monitoring/venv/bin/activate
    cd safir_monitoring/db/
    alembic upgrade head

5. Keystone Entegrasyonu
-------------------------

OpenStack admin olarak asagidaki komutlari calistirin::

    openstack user create safir_monitoring --password SAFIR_MONITORING_PASS
    openstack role add --project service --user safir_monitoring admin

Servis ve endpoint'leri olusturun::

    openstack service create monitoring \
        --name safir_monitoring \
        --description "Safir Monitoring Service"

    openstack endpoint create safir_monitoring \
        --region RegionOne public http://CONTROLLER_HOST:9768

    openstack endpoint create safir_monitoring \
        --region RegionOne admin http://CONTROLLER_HOST:9768

    openstack endpoint create safir_monitoring \
        --region RegionOne internal http://CONTROLLER_HOST:9768

6. Systemd Servisi
-------------------

Servis dosyasini kopyalayin ve etkinlestirin::

    sudo cp etc/safir_monitoring.service /etc/systemd/system/safir_monitoring.service
    sudo systemctl daemon-reload
    sudo systemctl enable safir_monitoring
    sudo systemctl start safir_monitoring

.. note::

   Servis root olarak calisir. Systemd servis dosyasi venv icindeki gunicorn'u
   kullanir (``/opt/safir_monitoring/venv/bin/gunicorn``). ``VIRTUAL_ENV`` ve
   ``PATH`` environment degiskenleri servis dosyasinda otomatik ayarlanir.

Servis durumunu kontrol edin::

    sudo systemctl status safir_monitoring

Dizin Yapisi
=============

Kurulum sonrasinda dosya sistemi asagidaki sekilde yapilandi:

::

    /opt/safir_monitoring/
    +-- venv/                          # Python virtual environment
    |   +-- bin/
    |   |   +-- python3                # venv Python yorumlayicisi
    |   |   +-- gunicorn               # ASGI sunucusu
    |   |   +-- alembic                # DB migration araci
    |   |   +-- activate               # venv aktivasyon scripti
    |   +-- lib/python3.x/site-packages/
    |       +-- safir_monitoring/      # Uygulama paketi
    |       +-- ...                    # Diger bagimliliklar

    /etc/safir_monitoring/
    +-- safir_monitoring.conf          # Ana konfigurasyon
    +-- gunicorn.py                    # Gunicorn ayarlari
    +-- api_paste.ini                  # WSGI pipeline

    /var/log/safir_monitoring/
    +-- safir_monitoring.log           # Servis loglari
    +-- safir_monitoring-error.log     # Gunicorn hata loglari
    +-- safir_monitoring-access.log    # Gunicorn erisim loglari

    /var/lib/thanos/rules/             # Thanos ruler kural dosyalari

Servis Yonetimi
================

Baslat / Durdur / Yeniden Baslat::

    sudo systemctl start safir_monitoring
    sudo systemctl stop safir_monitoring
    sudo systemctl restart safir_monitoring

Konfigurasyon degisikliginden sonra graceful reload::

    sudo systemctl reload safir_monitoring

Servis durumu::

    sudo systemctl status safir_monitoring
    journalctl -u safir_monitoring -f

Manuel calistirma (debug icin)::

    source /opt/safir_monitoring/venv/bin/activate
    gunicorn -c /etc/safir_monitoring/gunicorn.py \
        safir_monitoring.main:asgi_app\(''\) \
        --env oslo_config_file=/etc/safir_monitoring/safir_monitoring.conf \
        --env config_base_path=/etc/safir_monitoring/

API Endpoint'leri
==================

Servis basarili bir sekilde basladiktan sonra asagidaki endpoint'ler kullanilabilir:

**Temel URL:** ``http://CONTROLLER_HOST:9768/api/v1``

Mevcut endpoint'ler:

======================================  ======  ====================================
Endpoint                                Method  Aciklama
======================================  ======  ====================================
``/metrics``                            GET     PromQL ile zaman serisi sorgusu
``/metrics/list``                       GET     Metrik listesi (user/system)
``/metrics/measurements``               GET     Zaman serisi olcum verileri
``/metrics/statistics``                 GET     Aggregated istatistikler
``/metrics/names``                      GET     Metrik isimlerini listele
``/metrics/dimensions/names``           GET     Dimension (label) isimlerini listele
``/metrics/dimensions/values``          GET     Dimension degerlerini listele
``/metrics/hosts``                      GET     Host listesi (admin)
``/metrics/vms``                        GET     VM listesi
``/alarm-rules``                        GET     Alarm kurallari listesi
``/alarm-rules``                        POST    Yeni alarm kurali olustur
``/alarm-rules/{id}``                   PUT     Alarm kurali guncelle
``/alarm-rules/{id}``                   DELETE  Alarm kurali sil
``/alarm-rules/{id}/toggle``            POST    Alarm kuralini etkinlestir/devre disi birak
``/notifications``                      GET     Bildirim kanallari listesi
``/notifications``                      POST    Yeni bildirim kanali olustur
``/notifications/{id}``                 PUT     Bildirim kanali guncelle
``/notifications/{id}``                 DELETE  Bildirim kanali sil
``/alarm-history``                      GET     Alarm gecmisi
``/quotas``                             GET     Proje kaynak kotalari
``/host_quotas``                        GET     Host kotalari (admin)
``/alerts/webhook``                     POST    Alertmanager webhook (public)
======================================  ======  ====================================

Swagger UI
===========

Interaktif API dokumantasyonu icin::

    http://CONTROLLER_HOST:9768/docs

OpenAPI spec::

    http://CONTROLLER_HOST:9768/api/v1/openapi.json

Log Dosyalari
==============

==============  ====================================================
Log             Yol
==============  ====================================================
Servis          ``/var/log/safir_monitoring/safir_monitoring.log``
Gunicorn Error  ``/var/log/safir_monitoring/safir_monitoring-error.log``
Gunicorn Access ``/var/log/safir_monitoring/safir_monitoring-access.log``
==============  ====================================================

Canli log takibi::

    tail -f /var/log/safir_monitoring/safir_monitoring.log

Guncelleme
===========

Mevcut kurulumu guncellemek icin::

    cd safir_monitoring
    git pull origin master
    source /opt/safir_monitoring/venv/bin/activate
    pip install .
    pip install -r requirements.txt
    cd safir_monitoring/db && alembic upgrade head && cd ../..
    sudo systemctl restart safir_monitoring

Sorun Giderme
==============

Servis baslamiyor
------------------

1. Konfigurasyon dosyasini dogrulayin::

    cat /etc/safir_monitoring/safir_monitoring.conf

2. Veritabani baglantisini test edin::

    source /opt/safir_monitoring/venv/bin/activate
    python3 -c "import pymysql; pymysql.connect(host='DB_HOST', user='safir_monitoring', password='DB_PASS', database='safir_monitoring')"

3. Thanos erisimini test edin::

    curl http://THANOS_HOST:10903/api/v1/status/config

4. Detayli loglara bakin::

    journalctl -u safir_monitoring --no-pager -n 50

5. venv'in saglam oldugunu dogrulayin::

    /opt/safir_monitoring/venv/bin/python3 -c "import safir_monitoring; print('OK')"

Kimlik dogrulama hatalari
--------------------------

1. Keystone URL'inin dogru oldugunu dogrulayin::

    curl http://CONTROLLER_HOST/identity/v3

2. Servis kullanicisinin mevcut oldugunu dogrulayin::

    openstack user show safir_monitoring

Port cakismasi
--------------

Port 9768 baska bir servis tarafindan kullaniliyorsa::

    ss -tlnp | grep 9768

Farkli port kullanmak icin ``safir_monitoring.conf``, ``gunicorn.py`` ve
Keystone endpoint'lerini guncelleyin.

venv bozuldu
--------------

Virtual environment'i sifirdan olusturmak icin::

    sudo rm -rf /opt/safir_monitoring/venv
    sudo python3 -m venv /opt/safir_monitoring/venv
    source /opt/safir_monitoring/venv/bin/activate
    pip install --upgrade pip setuptools wheel
    cd /path/to/safir_monitoring
    pip install .
    pip install -r requirements.txt
    sudo systemctl restart safir_monitoring
