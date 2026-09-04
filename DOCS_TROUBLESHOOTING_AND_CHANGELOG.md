# 📘 OpenStack Safir Bulut & Türk Telekom Entegrasyonu
## Kurulum Süreci, Yaşanan Sorunlar, Çözümler ve Önemli Değişiklikler Raporu (Changelog)

Bu doküman; **OpenStack-Ansible (2024.1 Caracal / Ubuntu 24.04 / Python 3.12)** altyapısı üzerine geliştirilen **Safir All-in-One Enterprise Gözlemlenebilirlik ve Yönetim Platformu** kurulumunda karşılaşılan teknik zorlukları, kök nedenlerini ve uygulanan kurumsal çözümleri detaylandırmaktadır.

---

## 🏗️ 1. Genel Mimari ve Kurulan Bileşenler

| Faz | Bileşen Adı | Görevi / Açıklama | Uç Nokta / Port |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Dynamic Discovery & Pre-flight** | Ortamdaki LXC konteynerleri, IP'leri, ağ köprülerini ve Galera/RabbitMQ bilgilerini dinamik tespit eder. | - |
| **Phase 2** | **OpenSearch Stack** | Dağıtık log ve CADF denetim arama motoru (2.14.0) ve Web Paneli. | `9200` (REST) / `5601` (Dashboards) |
| **Phase 3** | **CADF Audit Middleware** | Nova, Cinder, Glance, Neutron, Heat ve Keystone boru hatlarına idempotent CADF denetim filtresi enjekte eder. | - |
| **Phase 4** | **SafirCloudWatcher** | RabbitMQ bildirimlerini dinler, CADF formatına dönüştürüp OpenSearch'e indeksler. | `8839` (REST API) |
| **Phase 5** | **SafirMonitoring** | Metrik toplama, Thanos/Prometheus entegrasyonu, alarm kural yönetimi ve FastAPI backend. | `9739` (FastAPI / Swagger) |
| **Phase 6** | **Grafana & Keystone Proxy** | Açık kaynak Grafana, hazır OpenStack panelleri ve Keystone Auth Proxy. | `3000` (Web UI) / `3001` (Proxy) |
| **Phase 7** | **Türk Telekom Skyline Dashboard** | Türk Telekom / TÜBİTAK BİLGEM özel React arayüzü (`skyline_console`) ve Python API sunucusu. | `9999` (Nginx) / `28000` (API) |
| **Phase 8** | **Prometheus Libvirt Exporter** | KVM/QEMU hipervizör ve VM metrik toplayıcısı (Go tabanlı). | `9177` (/metrics) |
| **Phase 9** | **Smoke Test & Verification** | Uçtan uca sağlık taraması, canlı CADF olay testi ve erişim raporu. | - |

---

## 🛠️ 2. Karşılaşılan Sorunlar ve Uygulanan Çözümler

### 1. Evrensel DNS Kuralı (LXC Konteyner İnternet / Ağ Erişimi)
* **Yaşanan Sorun:** LXC konteynerleri oluşturulurken `8.8.8.8` veya `10.0.3.1` gibi statik DNS IP'leri tanımlandığında, dış interneti kapalı veya sadece dahili DNS kullanan müşteri ağlarında paket indirme (apt/pip) ve servis çözümleme adımları askıda kalıyordu.
* **Uygulanan Çözüm:** 
  * Tüm rollerde statik DNS atamaları kaldırıldı.
  * Tüm LXC konteynerlerinin `/etc/resolv.conf` dosyasını doğrudan hedef fiziksel sunucudan devralması (`remote_src: true`) sağlandı.
  * Böylece sistem **herhangi bir müşteri ortamına sıfır müdahale ile uyumlu hale getirildi (Zero-Touch).**

---

### 2. Türk Telekom Skyline Dashboard Arayüzü ve Menü Görünürlüğü (Phase 7)
* **Sorun 1 (API Paketi Eksikliği):** `skyline-apiserver` paketi standart PyPI deposunda yer almadığı için `ModuleNotFoundError: No module named 'skyline_apiserver'` hatasıyla servis çöküyordu.
  * **Çözüm:** `roles/skyline_dashboard/tasks/main.yml` içinde API sunucusu OpenStack'in resmi deposundan (`git+https://opendev.org/openstack/skyline-apiserver.git`) kurulacak şekilde güncellendi.
* **Sorun 2 (Oturum / SQLite Veritabanı):** API sunucusu ayağa kalktığında ilk girişte oturum tablosu bulunamadığı için `401 Unauthorized` dönüyordu.
  * **Çözüm:** `METADATA.create_all(bind=engine)` ile SQLite tablolarının servis başlarken otomatik oluşturulması sağlanmıştır.

### 10. Skyline API Proxy & Nova CADF Audit Fix (Web Dashboard & Quotas)
- **Sorun 1 (Nginx API 404 & Barbican Döngüsü):**
  - Skyline React frontend'i Nova, Neutron, Cinder ve Glance çağrılarını `/api/openstack/regionone/...` yoluyla doğrudan Nginx üzerinden çekmek istiyordu. Nginx'te bu reverse-proxy blokları tanımlı olmadığı için tüm API çağrıları 404 alıyordu.
  - Ortamda Barbican kurulu olmadığı için `/v1/secrets` çağrıları sonsuz döngüye giriyordu.
  - **Çözüm:** `roles/skyline_dashboard/templates/nginx_skyline.conf.j2` dosyasına Nova (8774), Cinder (8776), Glance (9292), Neutron (9696), Heat (8004), Placement (8778) dinamik proxy yönlendirmeleri ve Barbican için zararsız JSON fallback eklendi.
- **Sorun 2 (Skyline Backend `interface_type`):**
  - `skyline.yaml` içerisinde `interface_type` varsayılan olarak `public` kaldığı için Skyline API server iç yönetim ağı yerine dış SSL adreslerine gitmeye çalışıyordu.
  - **Çözüm:** `roles/skyline_dashboard/templates/skyline.yaml.j2` ve `defaults/main.yml` içinde `interface_type: "internal"` olarak sabitlendi.
- **Sorun 3 (Nova API 503 & CADF Audit Map Eksikliği):**
  - Phase 3 CADF Audit Middleware konfigürasyonunda Nova'nın `api-paste.ini` dosyasına eklenen audit filtresi `/etc/nova/api_audit_map.conf` dosyasını arıyordu. Dosya LXC konteyner içinde bulunamadığı için Nova uWSGI worker'ları `FileNotFoundError` ile Segmentation Fault alıp çöküyordu.
  - **Çözüm:** `roles/cadf_audit_middleware/tasks/configure_service.yml` içinde `ansible.builtin.copy` yerine `lxc-attach` kullanılarak audit map dosyaları doğrudan konteynerlerin içine yazıldı ve servisler yeniden başlatıldı.
- **Sorun 4 (Placement API 502 Bad Gateway & Port 8780 Uyuşmazlığı):**
  - Genel Bakış (`/base/overview-admin`) sayfasında envanter ve kaynak sağlayıcılar çekilirken Nginx `502 Bad Gateway (Connection refused to 8778)` hatası alıyordu. React frontend'i envanter dizisini okuyamayınca `TypeError: Cannot read properties of undefined (reading 'map')` hatası veriyordu.
  - OpenStack-Ansible mimarisinde HAProxy Placement servisini 8778 yerine **8780** portunda çalıştırmaktadır.
  - **Çözüm:** `roles/skyline_dashboard/templates/nginx_skyline.conf.j2` dosyasındaki Placement proxy yönlendirmesi `http://{{ openstack_management_vip }}:8780/` olarak güncellendi.
- **Sorun 5 (OpenSearch Dashboards Port 5601 & Dinamik IP Keşfi):**
  - OpenSearch konteyneri birden fazla IP veya dinamik yönetim IP'si aldığında, HAProxy eski veya eşleşmeyen bir IP'yi (örn: `.215`) dinlemeye devam ettiği için `L4CON (Connection refused)` alıp `503 Service Unavailable` dönüyordu.
  - **Çözüm:** `roles/opensearch_stack/tasks/main.yml` içerisine HAProxy bloğundan önce konteynerin aktif dinleyen yönetim IP'sini dinamik tespit eden keşif adımı eklendi ve HAProxy gerçek IP (`.217`) ile güncellendi.

* **Sorun 4 (Safir Menülerinin Gizlenmesi):** Türk Telekom React frontend paketi (`skyline_console-7.1.0`), menüleri göstermeden önce `checkEndpoint` fonksiyonuyla Keystone servis kataloğunu sorguluyordu. Keystone'da eşleşmeyen servisler olduğunda **Göçmen (Migration), LogAuth (Log Management), Marketplace, Billing, API Gateway** gibi Türk Telekom modülleri arayüzde gizleniyordu.
  * **Çözüm (Hibrit Çözüm):**
    1. **Frontend Yaması:** `main.bundle.*.js` ve `basic.bundle.*.js` dosyalarındaki `checkEndpoint` fonksiyonu yamalanarak tüm Safir menülerinin panelde **her zaman ve koşulsuz görünmesi** sağlandı.
    2. **Keystone Kayıtları:** `safirmonitoring`, `safir_cloud_watcher`, `safirmigration`, `safirlogauth`, `safir_marketplace`, `billing`, `safir_apigateway` servis ve uç noktaları (public/internal/admin) Keystone kataloğuna otomatik eklendi.

---

### 3. Libvirt Exporter Offline Go Derleme Hatası (Phase 8)
* **Yaşanan Sorun:** Ubuntu 24.04 üzerinde yüklü gelen Go sürümü `go 1.22` iken, `prometheus-libvirt-exporter` kaynak kodundaki `go.mod` ve `vendor/modules.txt` dosyaları `go 1.24` / `go 1.23` gerektiriyordu. İnternet erişimi kısıtlı ortamlarda Go derleyicisi yeni sürüm indirmeye çalışıp `toolchain not available` hatası ile başarısız oluyordu.
* **Uygulanan Çözüm:**
  * `packages/prometheus-libvirt-exporter/go.mod` ve `vendor/modules.txt` içindeki Go sürüm direktifleri `1.22` seviyesine çekildi.
  * Derleme komutuna `export GOTOOLCHAIN=local` ve `export CGO_ENABLED=1` eklenerek yerel vendor kütüphaneleriyle **%100 offline derleme** sağlandı.

---

### 4. MariaDB / Galera Veritabanı Kullanıcı Yönetimi (Phase 5)
* **Yaşanan Sorun:** Ubuntu 24.04 üzerinde çalışan Galera konteyneri içinde standart MySQL Ansible modülleri veya karmaşık alt kabuklar (subshell) yetkilendirme hatasına düşüyordu.
* **Uygulanan Çözüm:**
  * MariaDB istemcisi üzerinden doğrudan standart SQL komutları (`CREATE DATABASE IF NOT EXISTS`, `CREATE USER IF NOT EXISTS`, `GRANT ALL PRIVILEGES`, `FLUSH PRIVILEGES`) çalıştırılarak idempotent ve sağlam bir veritabanı hazırlama adımı kuruldu.

---

### 5. Grafana Dashboard Jinja2 Ayrıştırma Çakışması (Phase 6)
* **Yaşanan Sorun:** Grafana dashboard JSON şablonunda (`openstack_overview.json.j2`) yer alan `${variable}` veya `{{...}}` Grafana değişkenleri, Ansible Jinja2 derleyicisi tarafından değişken olarak algılanıp derleme hatasına yol açıyordu.
* **Uygulanan Çözüm:**
  * JSON şablonu `{% raw %}` ... `{% endraw %}` blokları arasına alınarak Jinja2 çakışması önlendi.
  * `gpg --dearmor` komutuna `--yes` parametresi eklenerek TTY kilitlenmeleri engellendi.

---

### 6. Phase 9 Uçtan Uca Sağlık Doğrulaması & Dinamik Raporlama
* **Yaşanan Sorun:** Son aşamadaki sağlık testlerinde statik IP'ler (`172.29.236.152` vb.) kullanıldığında, dinamik LXC ortamlarında konteynerlerin farklı IP alması durumunda `No route to host` hatası alınıyordu.
* **Uygulanan Çözüm:**
  * Doğrulama rolünün (`roles/verification_report/tasks/main.yml`) başına dinamik IP keşif mekanizması entegre edildi.
  * Tüm sağlık kontrolleri resilient (esnek) hale getirilerek final raporunun her koşulda eksiksiz ekrana basılması sağlandı.

---

## 🚀 3. Dağıtım ve Çalıştırma Yönergesi

Herhangi bir yeni sunucuya veya müşteri ortamına kurulum yapmak için tek komut yeterlidir:

```bash
# 1. Depoyu çekin
git clone https://github.com/ogi-glk/openstack-safir.git
cd openstack-safir

# 2. Host envanterini belirleyin (inventory/hosts.ini)
# [openstack_host]
# target1 ansible_host=IP_ADRESI ansible_user=root

# 3. Kurulumu tek komutla başlatın
ansible-playbook -i inventory/hosts.ini playbooks/deploy_all.yml
```

---

## 🔑 4. Varsayılan Erişim Bilgileri Tablosu

* **Türk Telekom Skyline Web Paneli:** `http://<HOST_IP>:9999/` *(Kullanıcı: `admin` / Şifre: `a93b97960d21d3555d62c` / Domain: `Default`)*
* **Grafana Paneli:** `http://<HOST_IP>:3000/` *(Kullanıcı: `admin` / Şifre: `SafirGrafana123!`)*
* **OpenSearch Dashboards:** `http://<HOST_IP>:5601/` *(Kullanıcı: `admin` / Şifre: `SafirOpenSearch123!`)*
* **SafirMonitoring Swagger:** `http://<HOST_IP>:9739/docs`
* **Prometheus Libvirt Metrikleri:** `http://<HOST_IP>:9177/metrics`
