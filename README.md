# OpenStack Safir All-in-One Automation Suite

Automated, enterprise-grade Ansible orchestration suite for deploying **OpenSearch 2.x & Dashboards**, **SafirCloudWatcher**, **SafirMonitoring**, **CADF Audit Middleware**, **Grafana & Keystone Auth Proxy**, and **Thanos Metrics Integration** on an OpenStack-Ansible (OSA) All-in-One environment.

---

## 🏗️ Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│               HAProxy Load Balancer (Internal VIP: 172.29.236.101)     │
│        Port 5601  ──>  OpenSearch Dashboards (target2-opensearch)      │
│        Port 3000  ──>  Grafana & Keystone Auth Proxy (target2-grafana) │
│        Port 9739  ──>  SafirMonitoring API (target2-safirmonitoring)  │
│        Port 8839  ──>  SafirCloudWatcher API (target2-safircloudwatcher)│
└────────┬──────────────┬──────────────────┬──────────────────┬──────────┘
         │              │                  │                  │
         ▼              ▼                  ▼                  ▼
  [OpenSearch Stack]  [Grafana Stack] [SafirMonitoring]  [SafirCloudWatcher]
  172.29.236.152      172.29.236.153  172.29.236.151     172.29.236.150
  - OpenSearch 2.19   - Grafana OSS   - FastAPI / ML     - Event Consumer
  - Dashboards        - Keystone Auth - Gunicorn ASGI    - Processor
                        Proxy (3001)  - Thanos Querier   - Multi-vhost Rabbit
                                                         - Two-phase Indexer
                                                                ▲
                                                                │
                                      [ OpenStack Core Services CADF Events ]
                                      (Nova, Cinder, Glance, Neutron, Heat, Keystone)
```

---

## 📋 Prerequisites (Pre-flight Validation)

> [!IMPORTANT]
> This automation suite **does NOT** deploy the baseline OpenStack All-in-One cluster from scratch. 
> The target host **MUST already have an operational OpenStack-Ansible (OSA) AIO deployment** installed.
> 
> The playbook includes a dedicated **`prerequisites_check`** role that automatically validates:
> * **Host OS:** Ubuntu 22.04 LTS or 24.04 LTS
> * **LXC Runtime:** Operational `lxc-ls` command
> * **Network Bridges:** `br-mgmt` (172.29.236.0/22) and `lxcbr0` (10.0.3.0/24)
> * **Core Containers:** Nova, Cinder, Glance, Neutron, Keystone, Galera, RabbitMQ
> * **Keystone Identity Endpoint:** Reachable at `http://172.29.236.101:5000/v3`
> 
> If any baseline requirement is missing, the playbook safely aborts with an informative diagnostic error message.

---

## 📦 Directory & Role Structure

```text
openstack-safir/
├── ansible.cfg                      # Optimized Ansible settings (pipelining, timeouts)
├── setup.sh                         # Master one-click installer script
├── README.md                        # Documentation
├── inventory/
│   ├── hosts.ini                    # Inventory target definition
│   └── group_vars/
│       └── all.yml                  # Central configuration (IPs, Ports, Passwords)
├── playbooks/
│   └── deploy_all.yml               # Master orchestration playbook
└── roles/
    ├── prerequisites_check/         # Validates existing OpenStack AIO baseline
    ├── opensearch_stack/            # OpenSearch 2.x, Dashboards & HAProxy port 5601
    ├── cadf_audit_middleware/       # CADF Audit on Nova, Cinder, Glance, Neutron, Heat, Keystone
    ├── safir_cloud_watcher/         # RabbitMQ multi-vhost listeners & OpenSearch indexer
    ├── safir_monitoring/            # FastAPI, Gunicorn ASGI, ML forecasting & Thanos query
    ├── grafana_stack/               # Grafana, Keystone Token Auth Proxy & OpenStack Dashboards
    ├── skyline_dashboard/           # Modern OpenStack Web Console (React/TypeScript & FastAPI :9999)
    ├── libvirt_exporter/            # Prometheus Libvirt Exporter (VM vCPU & Memory Metrics :9177)
    └── verification_report/         # End-to-end smoke testing & summary report
```

---

## 🚀 Quick Start (One-Click Deployment)

### 1. Clone or Copy the Suite to the Deployer Host
```bash
git clone https://github.com/b3lab/openstack-safir.git /opt/openstack-safir
cd /opt/openstack-safir
```

### 2. Verify / Edit Global Variables
Inspect `inventory/group_vars/all.yml` to adjust passwords, IPs, or cluster settings if needed.

### 3. Run the Automated Installer
```bash
chmod +x setup.sh
./setup.sh
```

*(Or execute directly via Ansible):*
```bash
ansible-playbook -i inventory/hosts.ini playbooks/deploy_all.yml
```

---

## 🔍 Role Descriptions

### 1. `prerequisites_check`
Validates the presence of base OpenStack services, bridges, and LXC runtime. Prevents running on unsupported or uninitialized hosts.

### 2. `opensearch_stack`
* Configures `vm.max_map_count=262144` on host.
* Creates `target2-opensearch-container` (IP: `172.29.236.152`).
* Installs OpenSearch 2.19.6 and OpenSearch Dashboards.
* Disables the Dashboards security plugin for unauthenticated local portal access.
* Adds HAProxy frontend/backend for port `5601`.

### 3. `cadf_audit_middleware`
* Generates `api_audit_map.conf` for Nova, Cinder, Glance, Neutron, Heat.
* Injects `[filter:audit]` into `api-paste.ini` and attaches `audit` to Keystone pipeline chains.
* Configures `enable_proxy_headers_parsing = true` and `oslo_messaging_notifications` (`driver = messagingv2`).
* Configures native `notification_format = cadf` on Keystone.
* Restarts API services gracefully.

### 4. `safir_cloud_watcher`
* Dynamically collects RabbitMQ `transport_url` strings across all services.
* Grants `safir_cloud_watcher` permissions on all RabbitMQ vhosts (`nova`, `cinder`, `glance`, `neutron`, `heat`, `keystone`).
* Updates `[opensearch]` and writes all `messaging_urls` into `safir_cloud_watcher.conf`.
* Starts `safircloudwatcher-api`, `safircloudwatcher-event-manager`, `safircloudwatcher-processor`.

### 5. `safir_monitoring`
* Fixes PasteDeploy pipeline to use native FastAPI ASGI application (`pipeline = safir_monitoring`).
* Sets Gunicorn workers (`workers = 2`, `reuse_port = False`).
* Configures Thanos Querier endpoint (`querier_endpoint = "http://10.8.129.146:10903"`).
* Ensures HAProxy health check targets `/docs`.

### 6. `grafana_stack`
* Creates `target2-grafana-container` (IP: `172.29.236.153`).
* Installs Grafana OSS and enables `[auth.proxy]`.
* Deploys **Grafana Keystone Auth Proxy** (`proxy.py` on port `3001`).
* Provisions Thanos-Prometheus Data Source and **OpenStack Overview Dashboard**.
* Adds HAProxy frontend/backend for port `3000`.

### 7. `skyline_dashboard` (Modern OpenStack Web Console)
* **Frontend:** React / TypeScript single-page application (`skyline-console`) served statically via Nginx on port `9999`.
* **Backend:** FastAPI & Gunicorn ASGI server (`skyline-apiserver`) listening on port `28000` in an isolated Python 3.12 virtual environment (`/opt/skyline/venv`).
* **Authentication & Identity Integration:**
  * Connects directly to Keystone (`https://10.8.135.9:5000/v3` or internal VIP) with `RegionOne` and `Default` domain scoping.
  * Resolves pre-login domain listing (`/api/v1/contrib/domains`) via automated middleware whitelisting and unauthenticated endpoint patching in `skyline_apiserver/main.py` and `contrib.py`.
* **Database & Session Engine:**
  * Auto-initializes SQLite schema (`revoked_token`, `settings`) in `/var/lib/skyline/skyline.db` on boot via `METADATA.create_all(bind=engine)` hook.
  * Manages user tokens, JWT profiles, and policy rules seamlessly.
* **Nginx Reverse Proxy:**
  * Configured with case-insensitive regex routing (`/api/openstack/skyline/`, `/api/openstack/.*keystone/`, `/api/`) and SPA fallback (`try_files $uri /index.html;`) to prevent `301` redirect loops.
* **System Services:** Managed via systemd units (`skyline-apiserver.service`, `nginx.service`).

### 8. `libvirt_exporter` (Hypervisor & VM Metrics)
* Compiles and installs `prometheus-libvirt-exporter` on the host/hypervisor.
* Connects to local hypervisor via `qemu:///system` Unix socket.
* Extracts agentless, kernel-level vCPU, memory, disk, and network metrics for all tenant virtual machines.
* Exposes standard Prometheus metrics on port `9177` (`http://0.0.0.0:9177/metrics`).
* Managed via systemd unit `prometheus-libvirt-exporter.service`.

### 9. `verification_report`
Runs automated smoke tests across all endpoints, creates/deletes a live OpenStack test resource, verifies OpenSearch index creation (`events-*`, `audit_events-*`), verifies Skyline dashboard availability on port 9999, verifies Libvirt exporter metrics on port 9177, and prints a comprehensive summary dashboard.

