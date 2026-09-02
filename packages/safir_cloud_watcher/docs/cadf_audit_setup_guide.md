# OpenStack CADF Audit Middleware Kurulum Rehberi

Bu dokuman, OpenStack servislerinde CADF (Cloud Auditing Data Federation) audit middleware'in nasil aktive edilecegini adim adim aciklar. Audit middleware, her API cagrisinda kim, nereden, ne zaman, ne yapti bilgilerini yakalayarak RabbitMQ'ya notification olarak gonderir.

---

## Genel Gereksinimler

Tum servislerde ortak olarak su adimlar uygulanir:

1. **Audit map dosyasi** olusturulur (`api_audit_map.conf`)
2. **api-paste.ini**'ye audit filter tanimlanir ve pipeline'a eklenir
3. **Servis conf** dosyasina `oslo_middleware` ayari eklenir
4. Servis **restart** edilir

### Onemli Uyarilar

- Pipeline satirlari **mutlaka tek satirda** olmalidir. Satir kirilirsa parse hatasi verir ve servis baslamaz.
- Degisiklik oncesi mevcut dosyalari yedekleyin: `cp api-paste.ini api-paste.ini.bak`
- `ignore_req_list = GET,HEAD` ayari ile sadece degisiklik yapan istekler (POST, PUT, DELETE, PATCH) audit edilir.
- `pycadf` paketinin servis venv'inde kurulu oldugunu dogrulayin: `pip show pycadf`

---

## 1. Nova (Compute)

### 1.1 Audit Map Dosyasi

`/etc/nova/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = compute

[path_keywords]
servers = server_id
flavors = flavor_id
images = image_id
os-keypairs = keypair_name
os-availability-zone = zone_id
os-aggregates = aggregate_id
os-hypervisors = hypervisor_id
os-migrations = migration_id
os-server-groups = server_group_id

[service_endpoints]
compute = service/compute
```

### 1.2 api-paste.ini Degisiklikleri

`/etc/nova/api-paste.ini` dosyasina filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/nova/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Keystone pipeline'larina `keystonecontext` sonrasina `audit` ekleyin (tek satirda):

```ini
[composite:openstack_compute_api_v21]
use = call:nova.api.auth:pipeline_factory_v21
keystone = cors http_proxy_to_wsgi compute_req_id faultwrap request_log sizelimit osprofiler authtoken keystonecontext audit osapi_compute_app_v21
noauth2 = cors http_proxy_to_wsgi compute_req_id faultwrap request_log sizelimit osprofiler noauth2 osapi_compute_app_v21

[composite:openstack_compute_api_v21_legacy_v2_compatible]
use = call:nova.api.auth:pipeline_factory_v21
keystone = cors http_proxy_to_wsgi compute_req_id faultwrap request_log sizelimit osprofiler authtoken keystonecontext audit legacy_v2_compatible osapi_compute_app_v21
noauth2 = cors http_proxy_to_wsgi compute_req_id faultwrap request_log sizelimit osprofiler noauth2 legacy_v2_compatible osapi_compute_app_v21
```

**Not:** Sadece `keystone` pipeline'larina ekleyin, `noauth2` pipeline'larina eklemeye gerek yok.

### 1.3 nova.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 1.4 Restart

```bash
systemctl restart nova-api
# veya uwsgi kullaniliyorsa
systemctl restart nova-api-os-compute
```

### 1.5 Dogrulama

```bash
openstack server list
journalctl -u nova-api --since "1 minute ago" | grep -i "audit"
```

---

## 2. Cinder (Block Storage)

### 2.1 Audit Map Dosyasi

`/etc/cinder/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = volume

[path_keywords]
volumes = volume_id
snapshots = snapshot_id
backups = backup_id
types = type_id
transfers = transfer_id
attachments = attachment_id
groups = group_id

[service_endpoints]
volume = service/volume
volumev3 = service/volume
```

### 2.2 api-paste.ini Degisiklikleri

`/etc/cinder/api-paste.ini` dosyasina filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/cinder/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Keystone pipeline'larina `keystonecontext` sonrasina `audit` ekleyin (tek satirda):

```ini
[composite:openstack_volume_api_v3]
use = call:cinder.api.middleware.auth:pipeline_factory
noauth = request_id cors http_proxy_to_wsgi faultwrap sizelimit osprofiler noauth apiv3
noauth_include_project_id = request_id cors http_proxy_to_wsgi faultwrap sizelimit osprofiler noauth_include_project_id apiv3
keystone = request_id cors http_proxy_to_wsgi faultwrap sizelimit osprofiler authtoken keystonecontext audit apiv3
keystone_nolimit = request_id cors http_proxy_to_wsgi faultwrap sizelimit osprofiler authtoken keystonecontext audit apiv3
```

### 2.3 cinder.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

**Onemli:** `[audit_middleware_notifications]` bolumunu cinder.conf'a **eklemeyin** — Cinder baslangicta bu bolumu okumaya calisirken timeout'a dusebilir.

### 2.4 Restart

```bash
systemctl restart cinder-api
# veya uwsgi kullaniliyorsa
systemctl restart cinder-wsgi-public
```

### 2.5 Dogrulama

```bash
openstack volume list
journalctl -u cinder-api --since "1 minute ago" | grep -i "audit"
```

---

## 3. Glance (Image)

### 3.1 Audit Map Dosyasi

`/etc/glance/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = image

[path_keywords]
images = image_id

[service_endpoints]
image = service/image
```

### 3.2 api-paste.ini Degisiklikleri

Glance'in paste dosyasi `/etc/glance/glance-api-paste.ini` veya pipeline composite yapisi `[composite:api]` altindadir.

Filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/glance/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Keystone pipeline'larina `context` sonrasina `audit` ekleyin (tek satirda):

```ini
[composite:api]
paste.composite_factory = glance.api:pipeline_factory
default = cors http_proxy_to_wsgi versionnegotiation osprofiler unauthenticated-context rootapp
caching = cors http_proxy_to_wsgi versionnegotiation osprofiler unauthenticated-context cache rootapp
cachemanagement = cors http_proxy_to_wsgi versionnegotiation osprofiler unauthenticated-context cache cachemanage rootapp
keystone = cors http_proxy_to_wsgi versionnegotiation osprofiler authtoken context audit rootapp
keystone+caching = cors http_proxy_to_wsgi versionnegotiation osprofiler authtoken context audit cache rootapp
keystone+cachemanagement = cors http_proxy_to_wsgi versionnegotiation osprofiler authtoken context audit cache cachemanage rootapp
```

### 3.3 glance-api.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 3.4 Restart

```bash
systemctl restart glance-api
```

### 3.5 Dogrulama

```bash
openstack image list
journalctl -u glance-api --since "1 minute ago" | grep -i "audit"
```

---

## 4. Neutron (Networking)

### 4.1 Audit Map Dosyasi

`/etc/neutron/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = network

[path_keywords]
networks = network_id
subnets = subnet_id
ports = port_id
routers = router_id
floatingips = floatingip_id
security-groups = security_group_id
security-group-rules = security_group_rule_id

[service_endpoints]
network = service/network
```

### 4.2 api-paste.ini Degisiklikleri

Neutron'un paste dosyasi `/etc/neutron/api-paste.ini`'dir.

Once mevcut dosyayi kontrol edin:

```bash
cat -n /etc/neutron/api-paste.ini
```

Filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/neutron/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Keystone pipeline'ina `keystonecontext` sonrasina `audit` ekleyin (tek satirda). Neutron'un pipeline yapisi farkli olabilir, ornek:

```ini
[composite:neutronapi_v2_0]
use = call:neutron.auth:pipeline_factory
noauth = cors http_proxy_to_wsgi request_id catch_errors extensions neutronapiapp_v2_0
keystone = cors http_proxy_to_wsgi request_id catch_errors authtoken keystonecontext audit extensions neutronapiapp_v2_0
```

**Not:** Neutron pipeline yapisi versiyona gore degisebilir. `cat -n` ile mevcut yapiya bakip `keystonecontext` sonrasina `audit` eklenmeli.

### 4.3 neutron.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 4.4 Restart

```bash
systemctl restart neutron-server
```

### 4.5 Dogrulama

```bash
openstack network list
journalctl -u neutron-server --since "1 minute ago" | grep -i "audit"
```

---

## 5. Heat (Orchestration)

### 5.1 Audit Map Dosyasi

`/etc/heat/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = orchestration

[path_keywords]
stacks = stack_id
resources = resource_name
events = event_id
snapshots = snapshot_id
templates = template_id

[service_endpoints]
orchestration = service/orchestration
```

### 5.2 api-paste.ini Degisiklikleri

Heat'in paste dosyasi `/etc/heat/api-paste.ini`'dir.

Once mevcut dosyayi kontrol edin:

```bash
cat -n /etc/heat/api-paste.ini
```

Filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/heat/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Pipeline'a `context` veya `keystonecontext` sonrasina `audit` ekleyin (tek satirda). Ornek:

```ini
[pipeline:heat-api]
pipeline = cors request_id faultwrap http_proxy_to_wsgi versionnegotiation osprofiler authurl authtoken context audit apiv1app
```

**Not:** Heat pipeline yapisi versiyona gore degisebilir. `cat -n` ile mevcut yapiya bakin.

### 5.3 heat.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 5.4 Restart

```bash
systemctl restart heat-api
```

### 5.5 Dogrulama

```bash
openstack stack list
journalctl -u heat-api --since "1 minute ago" | grep -i "audit"
```

---

## 6. Magnum (Container Infrastructure)

### 6.1 Audit Map Dosyasi

`/etc/magnum/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = container-infra

[path_keywords]
clusters = cluster_id
clustertemplates = clustertemplate_id
nodegroups = nodegroup_id

[service_endpoints]
container-infra = service/container-infra
```

### 6.2 api-paste.ini Degisiklikleri

Magnum'un paste dosyasi `/etc/magnum/api-paste.ini`'dir.

Once mevcut dosyayi kontrol edin:

```bash
cat -n /etc/magnum/api-paste.ini
```

Filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/magnum/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Pipeline'a `keystonecontext` veya uygun auth filter sonrasina `audit` ekleyin (tek satirda).

### 6.3 magnum.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 6.4 Restart

```bash
systemctl restart magnum-api
```

### 6.5 Dogrulama

```bash
openstack coe cluster list
journalctl -u magnum-api --since "1 minute ago" | grep -i "audit"
```

---

## 7. Octavia (Load Balancer)

### 7.1 Audit Map Dosyasi

`/etc/octavia/api_audit_map.conf`:

```ini
[DEFAULT]
target_endpoint_type = load-balancer

[path_keywords]
loadbalancers = loadbalancer_id
listeners = listener_id
pools = pool_id
members = member_id
healthmonitors = healthmonitor_id
l7policies = l7policy_id
l7rules = l7rule_id
amphora = amphora_id

[service_endpoints]
load-balancer = service/load-balancer
```

### 7.2 api-paste.ini Degisiklikleri

Octavia'nin paste dosyasi `/etc/octavia/api-paste.ini`'dir.

Once mevcut dosyayi kontrol edin:

```bash
cat -n /etc/octavia/api-paste.ini
```

Filter ekleyin:

```ini
[filter:audit]
paste.filter_factory = keystonemiddleware.audit:filter_factory
audit_map_file = /etc/octavia/api_audit_map.conf
ignore_req_list = GET,HEAD
```

Pipeline'a `keystonecontext` sonrasina `audit` ekleyin (tek satirda).

### 7.3 octavia.conf Degisiklikleri

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

Notification driver'in aktif oldugunu dogrulayin:

```ini
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

### 7.4 Restart

```bash
systemctl restart octavia-api
```

### 7.5 Dogrulama

```bash
openstack loadbalancer list
journalctl -u octavia-api --since "1 minute ago" | grep -i "audit"
```

---

## 8. Keystone (Identity)

Keystone Flask tabanli calistigi icin paste pipeline'a audit middleware **eklenemez**. Keystone kendi CADF notification mekanizmasini kullanir.

### 8.1 keystone.conf Degisiklikleri

```ini
[DEFAULT]
notification_format = cadf
notification_opt_out = identity.authenticate.pending
```

- `notification_format = cadf` tum Keystone notification'larini CADF formatinda gonderir
- `notification_opt_out = identity.authenticate.pending` servisler arasi surekli olusan token dogrulama event'lerini devre disi birakir

### 8.2 Restart

```bash
systemctl restart apache2
# veya
systemctl restart keystone-wsgi-public
```

### 8.3 Dogrulama

```bash
# Basarili login denemesi
openstack token issue
# Keystone vhost'unda notification queue kontrolu
rabbitmqctl list_queues -p keystone | grep notification
```

---

## Sorun Giderme

### Servis baslamiyor

```bash
journalctl -u <servis-adi> --since "5 minutes ago" | grep -i "error\|traceback"
```

En yaygin sebepler:
- Pipeline satiri kirilmis (tek satirda olmali)
- `api_audit_map.conf` dosya yolu yanlis
- `pycadf` paketi kurulu degil

### Audit event gelmiyor

```bash
# 1. Servis loglarinda audit uyarilari
journalctl -u <servis-adi> --since "5 minutes ago" | grep -i "audit\|skipping"

# 2. RabbitMQ'da notification queue'su var mi
rabbitmqctl list_queues -p <vhost> | grep notification

# 3. Notification driver aktif mi
grep -A3 "oslo_messaging_notifications" /etc/<servis>/<servis>.conf
```

### Yanlis Client IP geliyor

HAProxy arkasindan gelen isteklerde `X-Forwarded-For` header'inin iletildiginden emin olun:

```bash
# HAProxy config'inde
grep -i "forwardfor" /etc/haproxy/haproxy.cfg
```

Her servis conf dosyasinda:

```ini
[oslo_middleware]
enable_proxy_headers_parsing = true
```

### pycadf paketi kontrolu

```bash
# Ilgili servisin venv'inde
/openstack/venvs/<servis>/bin/pip show pycadf
```

Kurulu degilse:

```bash
/openstack/venvs/<servis>/bin/pip install pycadf
```

---

## Ozet Tablosu

| Servis | Audit Map Dosyasi | Pipeline Degisikligi | Conf Degisikligi | Restart Komutu |
|--------|------------------|---------------------|-----------------|----------------|
| Nova | /etc/nova/api_audit_map.conf | keystonecontext audit | nova.conf | systemctl restart nova-api |
| Cinder | /etc/cinder/api_audit_map.conf | keystonecontext audit | cinder.conf | systemctl restart cinder-api |
| Glance | /etc/glance/api_audit_map.conf | context audit | glance-api.conf | systemctl restart glance-api |
| Neutron | /etc/neutron/api_audit_map.conf | keystonecontext audit | neutron.conf | systemctl restart neutron-server |
| Heat | /etc/heat/api_audit_map.conf | context audit | heat.conf | systemctl restart heat-api |
| Magnum | /etc/magnum/api_audit_map.conf | keystonecontext audit | magnum.conf | systemctl restart magnum-api |
| Octavia | /etc/octavia/api_audit_map.conf | keystonecontext audit | octavia.conf | systemctl restart octavia-api |
| Keystone | Gerekmiyor | Gerekmiyor | keystone.conf | systemctl restart apache2 |
