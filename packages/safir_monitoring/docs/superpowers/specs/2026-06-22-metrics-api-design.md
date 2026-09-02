# Safir Monitoring — Metrics API Tasarim Spesifikasyonu

**Tarih:** 2026-06-22
**Durum:** Onaylandi
**Temel Referans:** monasca-api metrics endpoint'leri

## Ozet

safir_monitoring servisine monasca-api'nin metrics endpoint'leri baz alinarak yeni API'ler eklenmesi planlanmaktadir. Uygulama 3 fazda gerceklestirilecektir. Mevcut endpoint'ler (`GET /metrics`, `GET /metrics/list`) korunacaktir.

## Kararlar

- **Kullanici kitlesi:** Hem admin hem tenant (project owner)
- **Backend:** Sadece Thanos (mevcut yapi korunacak)
- **Dimension API:** PromQL bilmeyen kullanicilar icin dimension endpoint'leri sunulacak
- **Forecasting hesaplama:** Python uygulama katmaninda yapilacak
- **Endpoint tasarimi:** monasca-api'deki resource_type bazli ayri endpoint'ler yerine parametrik, birlesmis endpoint'ler kullanilacak

## Mevcut Endpoint'ler (Korunacak)

| Endpoint | Method | Aciklama |
|----------|--------|----------|
| `GET /api/v1/metrics` | GET | Thanos'tan PromQL ile zaman serisi sorgusu |
| `GET /api/v1/metrics/list` | GET | Mevcut metrikleri listeleme (user/system) |

Bu endpoint'ler mevcut islevselliklerini aynen koruyacaktir.

---

## Faz 1 — Temel Metrik API'leri

### Endpoint Listesi

| Endpoint | Method | Aciklama | Erisim |
|----------|--------|----------|--------|
| `GET /api/v1/metrics/measurements` | GET | Zaman serisi olcum verileri | admin + tenant |
| `GET /api/v1/metrics/statistics` | GET | Aggregated istatistikler | admin + tenant |
| `GET /api/v1/metrics/names` | GET | Mevcut metrik isimlerini listele | admin + tenant |
| `GET /api/v1/metrics/dimensions/names` | GET | Belirli bir metrik icin label key'lerini listele | admin + tenant |
| `GET /api/v1/metrics/dimensions/values` | GET | Belirli bir label key icin mevcut degerleri listele | admin + tenant |
| `GET /api/v1/metrics/hosts` | GET | Metrik gonderen host'lari listele | admin |
| `GET /api/v1/metrics/vms` | GET | Metrik gonderen VM'leri listele | admin + tenant |

### Ortak Parametreler

Tum endpoint'lerde kullanilabilecek parametreler:

- `name` (string) — Metrik adi (measurements ve statistics icin zorunlu)
- `dimensions` (string) — Label filtresi, `key:value,key2:value2` formatinda
- `start_time` / `end_time` (ISO8601) — Zaman araligi
- `limit` / `offset` — Sayfalama

### Endpoint Detaylari

#### `GET /metrics/measurements`

- Ek parametreler: `step` (varsayilan 5m), `merge_metrics` (boolean)
- Thanos'a `query_range` API'si ile PromQL sorgusu gonderir
- Tenant kullanicilar icin otomatik `project_id` filtresi enjekte edilir (mevcut yapidaki gibi)
- Yanit:

```json
{
  "name": "cpu.utilization",
  "dimensions": {"hostname": "host1"},
  "measurements": [[1719014400, 65.3], [1719014700, 67.1]]
}
```

#### `GET /metrics/statistics`

- Ek parametreler:
  - `statistics` (zorunlu) — avg, min, max, count, sum (virgul ile ayrilmis)
  - `period` (saniye cinsinden aggregation periyodu)
- Thanos'a PromQL aggregation fonksiyonlari ile sorgu yapar (orn: `avg_over_time`, `max_over_time`)
- Yanit:

```json
{
  "name": "cpu.utilization",
  "dimensions": {"hostname": "host1"},
  "statistics": [[1719014400, 65.3, 12.1, 98.7, 288, 18806.4]]
}
```

Kolon sirasi: `[timestamp, avg, min, max, count, sum]`

#### `GET /metrics/names`

- Thanos `/api/v1/label/__name__/values` endpoint'ini kullanir
- `type` parametresi (user/system) korunur
- Yanit:

```json
{
  "metric_names": ["cpu.utilization", "mem.usable_perc", "disk.usage"]
}
```

#### `GET /metrics/dimensions/names`

- Parametre: `name` (metrik adi — zorunlu)
- Thanos `/api/v1/labels` endpoint'ini kullanir
- Yanit:

```json
{
  "dimension_names": ["hostname", "instance", "job"]
}
```

#### `GET /metrics/dimensions/values`

- Parametreler: `name` (metrik adi), `dimension_name` (label key — zorunlu)
- Thanos `/api/v1/label/<label_name>/values` endpoint'ini kullanir
- Yanit:

```json
{
  "dimension_name": "hostname",
  "dimension_values": ["host1", "host2", "host3"]
}
```

#### `GET /metrics/hosts`

- Thanos'tan `node_uname_info` metriginden host listesini ceker
- Sadece admin erisimi
- Yanit:

```json
{
  "elements": [
    {"name": "host1", "dimensions": {"instance": "10.0.0.1:9100", "job": "node"}}
  ]
}
```

#### `GET /metrics/vms`

- Thanos'tan `libvirt_domain_info` metriginden VM listesini ceker
- Tenant kullanicilar sadece kendi VM'lerini gorur
- Yanit:

```json
{
  "elements": [
    {"name": "web-server-1", "instance_id": "abc-123", "project_id": "...", "dimensions": {}}
  ]
}
```

---

## Faz 2 — Operasyonel Gorunurluk

### Endpoint Listesi

| Endpoint | Method | Aciklama | Erisim |
|----------|--------|----------|--------|
| `GET /api/v1/metrics/statistics/top-n-host` | GET | En yuksek metrik degerine sahip N host | admin |
| `GET /api/v1/metrics/statistics/top-n-vm` | GET | En yuksek metrik degerine sahip N VM | admin + tenant |
| `GET /api/v1/metrics/forecasts/wow-change` | GET | Haftalik degisim karsilastirmasi (Week-over-Week) | admin + tenant |

### Endpoint Detaylari

#### `GET /metrics/statistics/top-n-host`

- Parametreler:
  - `name` (zorunlu) — Metrik adi (orn: `cpu.idle_perc`, `mem.usable_perc`)
  - `n` (zorunlu) — Kac sonuc donsun (varsayilan: 10)
  - `statistics` (zorunlu) — Siralama kriteri: `avg`, `max`, `min`
  - `start_time` / `end_time` — Zaman araligi
- Thanos'ta `topk()` PromQL fonksiyonu ile hesaplanir
- Yanit:

```json
{
  "elements": [
    {"hostname": "host1", "value": 95.2, "dimensions": {"instance": "10.0.0.1:9100"}}
  ]
}
```

#### `GET /metrics/statistics/top-n-vm`

- Parametreler: top-n-host ile ayni
- Tenant kullanicilar sadece kendi VM'lerini gorur (otomatik `project_id` filtresi)
- `libvirt_` prefix'li metrikler uzerinden calisir
- Yanit:

```json
{
  "elements": [
    {"vm_name": "vm1", "instance_id": "abc-123", "value": 87.5, "dimensions": {}}
  ]
}
```

#### `GET /metrics/forecasts/wow-change`

- Parametreler:
  - `name` (zorunlu) — Metrik adi
  - `dimensions` — Label filtresi
  - `statistics` — Karsilastirma kriteri (varsayilan: `avg`)
- Hesaplama: Thanos'tan bu hafta ve gecen haftanin ayni zaman dilimi verileri cekilir, Python tarafinda fark ve yuzdesel degisim hesaplanir
- Yanit:

```json
{
  "name": "cpu.utilization",
  "dimensions": {"hostname": "host1"},
  "current_week_avg": 72.5,
  "previous_week_avg": 65.3,
  "change": 7.2,
  "change_percent": 11.02
}
```

### Kullanim Senaryolari

- **Top-N Host:** "CPU'su en yuksek 10 fiziksel sunucu hangisi?" — kapasite planlama ve sorun tespiti
- **Top-N VM:** "En cok kaynak tuketen VM'lerim hangileri?" — tenant self-servis optimizasyon
- **WoW Change:** "Bu hafta gecen haftaya gore kaynak tuketimi artti mi?" — trend takibi ve erken uyari

---

## Faz 3 — Forecasting & Rightsizing

### Forecasting Endpoint'leri

| Endpoint | Method | Aciklama | Erisim |
|----------|--------|----------|--------|
| `GET /api/v1/metrics/forecasts/prediction` | GET | Belirli host/VM icin kaynak tahmini | admin + tenant |
| `GET /api/v1/metrics/forecasts/prediction/system` | GET | Tum sistem geneli kaynak tahmini | admin |
| `GET /api/v1/metrics/forecasts/prediction/system/report` | GET | Sistem geneli tahmin raporu (tum kaynaklar) | admin |
| `GET /api/v1/metrics/forecasts/trend-graph` | GET | Belirli host/VM icin trend grafigi verisi | admin + tenant |
| `GET /api/v1/metrics/forecasts/trend-graph/system` | GET | Tum sistem geneli trend grafigi verisi | admin |
| `GET /api/v1/metrics/forecasts/max-value` | GET | Belirli host/VM icin tahmini maksimum deger | admin + tenant |

### Forecasting Ortak Parametreler

- `resource_type` (zorunlu) — `cpu`, `memory`, `disk`
- `period_days` — Tahmin periyodu (varsayilan: 30)
- `start_time` / `end_time` — Gecmis veri araligi (model girdisi)

### Forecasting Detaylari

#### `GET /metrics/forecasts/prediction`

- Ek parametreler: `dimension` (zorunlu — hostname veya instance_id)
- Hesaplama: Thanos'tan gecmis veri cekilir, Python'da linear regression veya moving average ile gelecek tahmini uretilir
- Yanit:

```json
{
  "resource_type": "cpu",
  "dimension": "host1",
  "current_avg": 65.3,
  "predicted_avg": 78.1,
  "predicted_peak": 92.4,
  "confidence": 0.85,
  "predictions": [[1719014400, 78.1], [1719100800, 79.3]]
}
```

#### `GET /metrics/forecasts/prediction/system`

- Tum host'larin toplam/ortalama kaynak kullanimi uzerinden tahmin
- Yanit yapisi `prediction` ile ayni, `dimension` yerine `"scope": "system"` doner

#### `GET /metrics/forecasts/prediction/system/report`

- CPU, memory ve disk tahminlerini tek seferde doner
- Yanit:

```json
{
  "report": {
    "cpu": {"current_avg": 45.2, "predicted_avg": 52.1, "predicted_peak": 71.0},
    "memory": {"current_avg": 62.0, "predicted_avg": 68.5, "predicted_peak": 85.3},
    "disk": {"current_avg": 38.7, "predicted_avg": 42.1, "predicted_peak": 55.0}
  },
  "period_days": 30
}
```

#### `GET /metrics/forecasts/trend-graph`

- Ek parametreler: `dimension` (zorunlu), `step` (grafik cozunurlugu, varsayilan: `1h`)
- Gecmis veri + tahmin egrisini birlestirir (UI grafik bileseni icin)
- Yanit:

```json
{
  "resource_type": "memory",
  "dimension": "host1",
  "historical": [[1719014400, 62.1], [1719018000, 63.5]],
  "forecast": [[1719100800, 68.2], [1719187200, 69.1]],
  "trend_line": [[1719014400, 62.0], [1719187200, 69.0]]
}
```

#### `GET /metrics/forecasts/trend-graph/system`

- Tum sistem geneli trend grafigi
- Yanit yapisi `trend-graph` ile ayni, `dimension` yerine `"scope": "system"` doner

#### `GET /metrics/forecasts/max-value`

- Ek parametreler: `dimension` (zorunlu)
- Tahmin periyodunda beklenen maksimum degeri doner
- Kapasite asimi riski degerlendirmesi icin kullanilir
- Yanit:

```json
{
  "resource_type": "cpu",
  "dimension": "host1",
  "current_max": 88.5,
  "predicted_max": 96.2,
  "period_days": 30
}
```

### Rightsizing Endpoint'leri

| Endpoint | Method | Aciklama | Erisim |
|----------|--------|----------|--------|
| `GET /api/v1/metrics/rightsizing/idle-vms` | GET | Atil VM'ler | admin + tenant |
| `GET /api/v1/metrics/rightsizing/over-provisioned-vms` | GET | Gereginden fazla kaynak ayrilmis VM'ler | admin + tenant |
| `GET /api/v1/metrics/rightsizing/under-provisioned-vms` | GET | Yetersiz kaynak ayrilmis VM'ler | admin + tenant |
| `GET /api/v1/metrics/rightsizing/report` | GET | Birlesik rightsizing raporu | admin + tenant |

### Rightsizing Ortak Parametreler

- `period_days` — Analiz periyodu (varsayilan: 7)
- `dimensions` — Ek filtreler

### Rightsizing Detaylari

#### `GET /metrics/rightsizing/idle-vms`

- Esik parametreleri: `cpu_threshold` (varsayilan: 5%), `memory_threshold` (varsayilan: 10%)
- Hesaplama: Thanos'tan belirtilen periyotta ortalama CPU ve memory kullanimi cekilir, esik altinda kalan VM'ler idle olarak isaretlenir
- Tenant kullanicilar sadece kendi VM'lerini gorur
- Yanit:

```json
{
  "idle_vms": [
    {
      "instance_id": "abc-123",
      "name": "web-server-3",
      "project_id": "...",
      "avg_cpu": 1.2,
      "avg_memory": 4.5,
      "allocated_vcpu": 4,
      "allocated_memory_gb": 8
    }
  ],
  "total_count": 12
}
```

#### `GET /metrics/rightsizing/over-provisioned-vms`

- Esik: `max_utilization_threshold` (varsayilan: 30%) — periyod boyunca maksimum kullanim bile bu esigin altindaysa over-provisioned
- Yanit: idle-vms ile ayni yapi + `recommendation` alani (onerilen vCPU/memory miktari)

```json
{
  "over_provisioned_vms": [
    {
      "instance_id": "def-456",
      "name": "db-backup",
      "project_id": "...",
      "max_cpu": 22.1,
      "max_memory": 28.3,
      "allocated_vcpu": 8,
      "allocated_memory_gb": 16,
      "recommendation": {"vcpu": 4, "memory_gb": 8}
    }
  ],
  "total_count": 34
}
```

#### `GET /metrics/rightsizing/under-provisioned-vms`

- Esik: `avg_utilization_threshold` (varsayilan: 80%) — ortalama kullanim bu esigin ustundeyse under-provisioned
- Yanit: over-provisioned ile ayni yapi, recommendation daha yuksek kaynaklar onerir

#### `GET /metrics/rightsizing/report`

- Tum kategorileri tek seferde doner + ozet istatistikler
- Yanit:

```json
{
  "summary": {
    "total_vms": 150,
    "idle": 12,
    "over_provisioned": 34,
    "under_provisioned": 8,
    "right_sized": 96
  },
  "idle_vms": [],
  "over_provisioned_vms": [],
  "under_provisioned_vms": [],
  "potential_savings": {
    "vcpu": 48,
    "memory_gb": 128
  }
}
```

---

## Tasarim Notlari

### monasca-api ile Farklar

- monasca-api her resource_type ve scope kombinasyonu icin ayri endpoint tanimlamis (prediction_cpu_by_hostname, prediction_memory_all_system, vb. — toplam ~18 endpoint). Bu tasarimda `resource_type` ve `dimension` parametreleri ile 6 forecasting endpoint'ine sikistirildi.
- monasca-api InfluxDB/Cassandra ve repository pattern kullaniyor. Bu tasarimda sadece Thanos kullanilacak.
- monasca-api'de metrik yazma (POST) endpoint'i var. Bu tasarimda metrikler Prometheus/Thanos tarafindan toplanir, yazma API'si yok.

### Yetkilendirme

- Mevcut oslo.policy ve Keystone middleware yapisi korunacak
- Admin endpoint'leri: hosts, top-n-host, prediction/system, trend-graph/system, prediction/system/report
- Tenant endpoint'lerinde otomatik `project_id` filtresi uygulanacak

### Forecasting Algoritmasi

- Implementasyon asamasinda netlestirilecek (linear regression, exponential smoothing, vb.)
- `confidence` alani modelin guvenilirligini belirtir

### Rightsizing Esikleri

- Kullanici tarafindan query parametresi olarak override edilebilir
- Varsayilan degerler konfigurasyondan okunur

---

## Toplam Endpoint Ozeti

| Faz | Yeni Endpoint Sayisi | Kapsam |
|-----|---------------------|--------|
| Mevcut | 2 | PromQL sorgu + metrik listeleme |
| Faz 1 | 7 | Measurements, statistics, names, dimensions, hosts/VMs |
| Faz 2 | 3 | Top-N, WoW change |
| Faz 3 | 10 | Forecasting (6) + Rightsizing (4) |
| **Toplam** | **22** | |
