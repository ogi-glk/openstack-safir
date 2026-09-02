# Safir Cloud Watcher - Event Pipeline Dokumantasyonu

## Genel Bakis

Safir Cloud Watcher, OpenStack servislerinden gelen notification'lari RabbitMQ uzerinden dinler, isler ve OpenSearch'e yazar. Ayrica opsiyonel olarak SIEM entegrasyonu icin syslog forwarding destekler.

## Mimari

```
OpenStack Servisleri (Nova, Cinder, Neutron, Keystone, Skyline...)
        |
        | oslo.messaging notifications
        v
    RabbitMQ (vhost bazli kuyruklar)
        |
        v
Safir Cloud Watcher Event Manager
        |
        |--- converter.py (notification -> Event donusumu, trait extraction)
        |--- opensearch.py (siniflandirma, enrichment, filtreleme, yazma)
        |
        +---> OpenSearch "audit_events" index (Phase 1)
        +---> OpenSearch "events" index (Phase 2)
        +---> Syslog Forward (opsiyonel, events index ile ayni veri)
        |
        v
    API (event.py) ---> UI (hidden_events filtreleme)
```

## Veri Akisi Adimlari

### Adim 1: Notification Alimi

Event Manager, RabbitMQ'daki `notifications.info` kuyrugunu dinler. Her OpenStack servisi kendi vhost'unda notification gonderir:

| Servis | RabbitMQ vHost | Ornek Event Type |
|--------|---------------|-----------------|
| Nova | nova | compute.instance.create.start |
| Cinder | cinder | volume.create.end |
| Neutron | neutron | port.create.end |
| Keystone | keystone | identity.authenticate |
| Glance | glance | image.create |
| Skyline | skyline | skyline.authenticate |

Dinlenen vhost'lar `safir_cloud_watcher.conf`'taki `[notification] messaging_urls` ile konfigure edilir.

### Adim 2: Notification -> Event Donusumu (converter.py)

`NotificationEventsConverter.to_event()` fonksiyonu notification body'sini Event objesine donusturur.

#### excluded_events.yaml Kontrolu

Once `excluded_events.yaml` kontrol edilir. Bu listedeki event type'lar tamamen drop edilir, hicbir yere yazilmaz:

```yaml
# excluded_events.yaml
- 'compute.instance.exists'
- 'backup.exists'
- 'volume.exists'
- 'snapshot.exists'
- 'capacity.backend'
```

#### Trait Extraction

Her event icin iki kaynaktan trait'ler cikarilir:

**DEFAULT_TRAITS** (tum event'lere uygulanir):

| Trait | Kaynak | Aciklama |
|-------|--------|----------|
| service | publisher_id | Hangi servis gondermis (nova-compute, cinder-volume...) |
| request_id | ctxt.request_id | Istegi tanimlayan unique ID |
| project_id | payload.tenant_id veya ctxt.project_id | Proje ID |
| user_id | payload.user_id veya ctxt.user_id | Kullanici ID (UUID) |
| tenant_id | payload.tenant_id veya ctxt.project_id | Eski terminoloji, project_id ile ayni |

**Event Type'a Ozel Trait'ler** (`event_definitions.yaml`'dan):

Ornek - `compute.instance.*`:

| Trait | Kaynak |
|-------|--------|
| display_name | payload.display_name |
| state | payload.state |
| instance_type | payload.instance_type |
| memory_mb | payload.memory_mb |
| vcpus | payload.vcpus |
| disk_gb | payload.disk_gb |
| host | publisher_id (split) |
| old_state | payload.old_state |
| availability_zone | payload.availability_zone |

Ornek - `*http.*` (audit middleware event'leri):

| Trait | Kaynak |
|-------|--------|
| initiator_name | payload.initiator.name |
| initiator_host_address | payload.initiator.host.address |
| initiator_request_id | payload.initiator.request_id |
| action | payload.action |
| outcome | payload.outcome |
| requestPath | payload.requestPath |
| target_id | payload.target.id |
| reason_code | payload.reason.reasonCode |

Ornek - `identity.authenticate` (Keystone CADF):

| Trait | Kaynak |
|-------|--------|
| initiator_name | payload.initiator.username |
| initiator_user_id | payload.initiator.user_id |
| initiator_id | payload.initiator.id |
| initiator_host_addr | payload.initiator.host.address |
| outcome | payload.outcome |

Ornek - `skyline.authenticate` (Skyline custom):

| Trait | Kaynak |
|-------|--------|
| user_name | payload.user_name |
| user_id | payload.user_id |
| client_ip | payload.client_ip |
| action | payload.action |
| outcome | payload.outcome |

### Adim 3: Siniflandirma ve Filtreleme (opensearch.py - record_events)

Event'ler uc kategoriye ayrilir:

```
Event geldi
  |
  +-- event_type "audit.http.*" ile basliyor mu?
  |     |
  |     +-- EVET: Audit Event --> audit_events index'ine yaz
  |     |
  |     +-- HAYIR: Devam et
  |
  +-- event_type "identity.authenticate" veya "skyline.authenticate" mi?
  |     |
  |     +-- EVET: Auth Event
  |     |     |
  |     |     +-- user_name bos mu? --> DROP
  |     |     +-- Servis kullanici mi? --> DROP
  |     |     +-- Gercek kullanici --> events index'ine yaz
  |     |
  |     +-- HAYIR: Devam et
  |
  +-- Standart Event --> events index'ine yaz
        |
        +-- Audit event'ten enrich et (request_id ile)
```

#### Servis Kullanici Filtreleme

`[notification] service_users` config parametresi ile tanimlanan kullanicilar **sadece authenticate event'lerinde** filtrelenir. Glob pattern destekler:

```ini
[notification]
service_users = nova,cinder,neutron,glance,heat,octavia,manila,magnum,masakari,zun,watcher,barbican,placement,swift,skyline,oltu-sa-*
```

Filtreleme sadece auth event'lerde uygulanir:

| Event Tipi | Filtreleme | Aciklama |
|-----------|-----------|----------|
| identity.authenticate | `initiator_name` trait ile | Servis kullanici veya user_name bos ise DROP |
| skyline.authenticate | `user_name` trait ile | Servis kullanici veya user_name bos ise DROP |
| audit.http.* | Filtreleme yok | Tum audit event'ler yazilir |
| Standart event'ler (compute, volume...) | Filtreleme yok | Tum event'ler user bagimsiz yazilir |

### Adim 4: Enrichment (Zenginlestirme)

Standart event'ler (compute, volume, network...) `request_id` uzerinden audit event'lerden zenginlestirilir.

#### Akis:

1. Audit event (`audit.http.request/response`) gelir -> `audit_events` index'ine yazilir -> index refresh edilir
2. Standart event gelir -> `request_id` ile `audit_events`'ten sorgu yapilir
3. Eslesme bulunursa su alanlar eklenir:

| Alan | Kaynak |
|------|--------|
| user_name | audit event'teki initiator_name |
| client_ip | audit event'teki initiator_host_address |
| action | audit event'teki action (create/update/delete) |
| outcome | audit event'teki outcome (success/failure) |
| request_path | audit event'teki requestPath (/v2.1/servers) |
| target_id | audit event'teki target_id |
| reason_code | audit event'teki reason_code (HTTP status) |

#### request_id Eslesmesi ve Cozumu

Audit middleware ve standart OpenStack notification'lari farkli `request_id` degerleri uretir:

- **Audit event**: `ctxt.request_id` kullanir — audit middleware `oslo_context.get_admin_context()` ile yeni bir context olusturur, bu da yeni bir UUID uretir
- **Standart event** (compute.instance.create vb.): `ctxt.request_id` kullanir — Nova/Cinder'in kendi request context'indeki orijinal ID

Bu iki ID birbirinden tamamen farklidir ve dogrudan eslesme yapilamaz.

**Cozum**: Audit middleware'in `_api.py` dosyasindaki `_create_event` metodunda orijinal request_id `payload.initiator.request_id` alaninda saklanir:

```python
# keystonemiddleware/audit/_api.py
initiator = ClientResource(
    ...
    request_id=req.environ.get('openstack.request_id'),  # Nova'nin orijinal req-xxx ID'si
    ...
)
```

Bu degeri yakalamak icin iki degisiklik yapildi:

**1. `event_definitions.yaml`'a trait eklendi:**

```yaml
- event_type: '*http.*'
  traits:
    ...
    initiator_request_id:
      fields: payload.initiator.request_id
```

**2. `opensearch.py`'de audit event yazilirken `initiator_request_id` kullanilir:**

```python
if self._is_audit_event(event.event_type):
    audit_request_id = traits.get("initiator_request_id", request_id)
    # audit_events index'e audit_request_id ile yazilir
```

Bu sayede:

```
Audit event:    request_id = "req-34cc1c70-..." (initiator_request_id'den)
Standart event: request_id = "req-34cc1c70-..." (ctxt.request_id'den)
                                    |
                                    +---> ESLESIYOR --> enrichment yapilabilir
```

Eger `initiator_request_id` trait'i bos gelirse (eski Keystone versiyonlari), fallback olarak `ctxt.request_id` kullanilir — bu durumda eslesmeme riski vardir.

#### Enrichment Basarisiz Oldugunda

Audit event henuz gelmemisse veya `request_id` eslesmemisse, standart event `user_name`, `client_ip` vb. alanlar olmadan yazilir.

### Adim 5: OpenSearch'e Yazma

#### events Index

SIEM'e aktarilan ana index. Tum standart event'ler ve auth event'ler buraya yazilir.

**Mapping:**

| Alan | Tip | Aciklama | Kaynak |
|------|-----|----------|--------|
| message_id | text | Unique event ID | Notification |
| project_id | text | Proje ID | DEFAULT_TRAITS |
| user_id | text | Kullanici UUID | DEFAULT_TRAITS veya CADF |
| user_name | keyword | Kullanici adi | Enrich veya CADF |
| resource_id | text | Kaynak UUID (VM, volume...) | Event trait |
| resource_type | text | Kaynak tipi (compute, volume...) | event_type'in ilk parcasi |
| display_name | text | Kaynak adi | Event trait |
| state | text | Mevcut durum (active, building...) | Event trait |
| old_state | keyword | Onceki durum | Event trait (sadece update) |
| request_id | keyword | Istek ID | DEFAULT_TRAITS |
| event_type | keyword | Event tipi | Notification |
| client_ip | ip | Client IP adresi | Enrich veya CADF |
| action | keyword | Yapilan islem | Enrich veya sabit |
| outcome | keyword | Sonuc (success/failure) | Enrich veya CADF |
| request_path | keyword | API endpoint | Enrich |
| target_id | keyword | Hedef servis | Enrich |
| reason_code | keyword | HTTP status kodu | Enrich |
| instance_type | keyword | Flavor adi | Compute event trait |
| memory_mb | integer | RAM (MB) | Compute event trait |
| vcpus | integer | CPU sayisi | Compute event trait |
| disk_gb | integer | Disk (GB) | Compute event trait |
| host | keyword | Compute node adi | Compute event trait |
| availability_zone | keyword | AZ | Compute/Volume trait |
| size | integer | Volume/image boyutu (GB) | Volume/Image trait |
| volume_type | keyword | Volume tipi | Volume trait |
| image_id | keyword | Image UUID | Volume trait |
| timestamp | date | Event zamani | Notification |

**Ornek - VM Olusturma (enrich edilmis):**

```json
{
  "event_type": "compute.instance.create.end",
  "display_name": "web-server-01",
  "resource_id": "29af6b99-d2ed-4c7b-88ef-f4ff5f049f7e",
  "resource_type": "compute",
  "state": "active",
  "instance_type": "m1.large",
  "memory_mb": 8192,
  "vcpus": 4,
  "disk_gb": 80,
  "host": "compute-node-03",
  "user_name": "admin",
  "client_ip": "10.15.65.85",
  "action": "create",
  "outcome": "success",
  "request_path": "/v2.1/servers",
  "reason_code": "202",
  "request_id": "req-34cc1c70-3ac8-4c83-8746-7e3fa5473fb0",
  "timestamp": "2026-06-21T09:33:43"
}
```

**Ornek - Login (Skyline):**

```json
{
  "event_type": "skyline.authenticate",
  "user_name": "yusuf",
  "user_id": "76c7f14fb9d14faa84175783529829e0",
  "client_ip": "10.15.65.85",
  "action": "login",
  "outcome": "success",
  "resource_type": "identity",
  "timestamp": "2026-06-21T14:30:00"
}
```

**Ornek - Login (Keystone):**

```json
{
  "event_type": "identity.authenticate",
  "user_name": "admin",
  "user_id": "d7cce4c0fd844838b3fe2f4b2bdc9b90",
  "client_ip": "10.13.10.121",
  "action": "authenticate",
  "outcome": "success",
  "resource_type": "identity",
  "timestamp": "2026-06-21T11:39:12"
}
```

#### audit_events Index

Audit middleware'den gelen HTTP request/response event'leri icin ara index. Standart event'leri zenginlestirmek icin kullanilir.

**Mapping:**

| Alan | Tip | Kaynak |
|------|-----|--------|
| message_id | text | Notification |
| project_id | text | CADF initiator.project_id |
| user_id | text | CADF initiator.id |
| user_name | keyword | CADF initiator.name |
| resource_id | text | Trait |
| resource_type | text | event_type'in ilk parcasi |
| request_id | keyword | CADF initiator.request_id |
| event_type | keyword | audit.http.request / audit.http.response |
| client_ip | ip | CADF initiator.host.address |
| action | keyword | create / update / delete |
| outcome | keyword | success / failure / pending |
| request_path | keyword | /v2.1/servers/uuid |
| target_id | keyword | nova / cinder / neutron |
| reason_code | keyword | HTTP status (200, 202, 404...) |
| timestamp | date | Notification |

### Adim 6: Syslog Forward (Opsiyonel)

`events` index'ine yazilan her event, config'te aktifse ayni zamanda remote syslog sunucusuna da gonderilir.

**Konfigurasyon:**

```ini
[syslog_forward]
enabled = false          # true yapilirsa aktif olur
host = 10.0.0.100       # SIEM syslog IP
port = 514              # Syslog port
protocol = udp           # udp veya tcp
facility = local0        # Syslog facility
```

**Mesaj Formati (RFC 5424):**

```
<134>1 2026-06-21T15:30:00.000000Z hostname safir-cloud-watcher event_manager - - {"event_type":"compute.instance.create.end","user_name":"admin","client_ip":"10.15.65.85",...}
```

Syslog forward hatasi OpenSearch yazimini etkilemez.

### Adim 7: API Katmani (event.py)

`GET /v1/events` endpoint'i `events` index'inden sorgulama yapar.

#### hidden_events.yaml

API response'tan gizlenen event type'lari. OpenSearch'te mevcuttur (SIEM erisebilir) ama UI'da gosterilmez:

```yaml
# hidden_events.yaml
- 'identity.authenticate'
- 'skyline.authenticate'
- 'audit.http.request'
- 'audit.http.response'
```

Bu filtreleme OpenSearch sorgusuna `must_not` clause olarak eklenir — pagination duzgun calisir.

#### API Response Alanlari

| Alan | Aciklama |
|------|----------|
| project_id | Proje ID |
| user_id | Kullanici UUID |
| resource_id | Kaynak UUID |
| resource_type | Kaynak tipi |
| display_name | Kaynak adi |
| request_id | Istek ID |
| event_type | Event tipi (start/end birlestirilir) |
| start_timestamp | Baslangic zamani |
| end_timestamp | Bitis zamani |
| duration | Sure (ms) |
| state | Durum |

## Konfigurasyon Dosyalari Ozeti

| Dosya | Konum | Amac |
|-------|-------|------|
| safir_cloud_watcher.conf | /etc/safir_cloud_watcher/ | Ana konfigurasyon |
| event_definitions.yaml | event/data/ | Trait tanimlari |
| excluded_events.yaml | event/data/ | Tamamen ignore edilen event'ler |
| hidden_events.yaml | event/data/ | UI'dan gizlenen event'ler |

## Filtreleme Katmanlari Ozeti

```
Notification geldi
  |
  [1] excluded_events.yaml --> DROP (hicbir yere yazilmaz)
  |
  [2] Siniflandirma
  |     |
  |     +-- audit.http.* --> audit_events index'ine yaz (filtreleme yok)
  |     |
  |     +-- identity/skyline.authenticate:
  |     |     +-- user_name bos mu? --> DROP
  |     |     +-- service_users filtresi --> DROP (servis kullanicisi ise)
  |     |     +-- Gercek kullanici --> events index'ine yaz
  |     |
  |     +-- Standart event'ler --> events index'ine yaz (filtreleme yok)
  |           +-- Audit event'ten enrich et (request_id ile)
  |
  [3] Syslog'a gonderilir (opsiyonel, sadece events)
  |
  [4] hidden_events.yaml --> API'den gizlenir (SIEM erisebilir)
```

## OpenStack Servis Konfigurasyonlari

Audit middleware'in calismasi icin her servisde su degisiklikler yapilmalidir:

### Nova / Cinder api-paste.ini

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/<servis>/api_audit_map.conf
ignore_req_list = GET,HEAD

[composite:openstack_..._api]
keystone = ... keystonecontext audit ...
```

### Servis .conf Dosyalari

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true

[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
transport_url = rabbit://...
```

### Keystone

```ini
[DEFAULT]
notification_format = cadf
notification_opt_out = identity.authenticate.pending
```

Keystone Flask tabanli oldugu icin paste pipeline'a audit middleware eklenemez. `identity.authenticate` event'leri Keystone'un kendi CADF notification mekanizmasiyla uretilir.

### Skyline

Skyline'a oslo.messaging entegrasyonu yapilarak `skyline.authenticate` event'leri login/logout sirasinda RabbitMQ'ya gonderilir. Gercek client IP `request.client.host` uzerinden alinir.
