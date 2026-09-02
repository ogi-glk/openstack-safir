#!/usr/bin/env python3
"""VM Metrics Collector — Thanos'tan VM metriklerini cekip MySQL'e yazar.

Systemd timer ile periyodik olarak calistirilir (varsayilan: her 1 saat).
API servisinden bagimsiz calisir, API worker'larini mesgul etmez.

Kullanim:
    python3 -m safir_monitoring.collector.metrics_collector \
        --config-file /etc/safirmonitoring/safirmonitoring.conf
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

import aiohttp
import pymysql
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# Thanos config
thanos_opts = [
    cfg.StrOpt('querier_endpoint',
               default='http://localhost:10903',
               help="Thanos Querier endpoint URL"),
]

db_opts = [
    cfg.StrOpt('connection',
               help="Database URL"),
]

CONF.register_opts(thanos_opts, group='thanos')
CONF.register_opts(db_opts, group='database')

# Collector-specific config
collector_opts = [
    cfg.IntOpt('retention_days',
               default=90,
               help="Eski verileri kac gun sonra sil"),
    cfg.IntOpt('query_timeout',
               default=120,
               help="Thanos sorgu timeout (saniye)"),
]
CONF.register_opts(collector_opts, group='collector')

# VM Thanos sorgu sablonlari
VM_QUERIES = {
    "avg_cpu": 'avg by(instance_id, instance_name, project_id, hostname) (libvirt_domain_cpu_utilization_perc)',
    "max_cpu": 'max by(instance_id, instance_name, project_id, hostname) (libvirt_domain_cpu_utilization_perc)',
    "avg_memory": 'avg by(instance_id, instance_name, project_id, hostname) (libvirt_domain_memory_stats_used_percent)',
    "max_memory": 'max by(instance_id, instance_name, project_id, hostname) (libvirt_domain_memory_stats_used_percent)',
    "disk_io": 'avg by(instance_id, instance_name, project_id, hostname) (safir_vm_disk_io_bytes_per_sec)',
    "net_io": 'avg by(instance_id, instance_name, project_id, hostname) (safir_vm_net_io_bytes_per_sec)',
    "allocated_vcpu": 'max by(instance_id, instance_name, project_id, hostname) (libvirt_domain_info_virtual_cpus)',
    "allocated_memory": 'max by(instance_id, instance_name, project_id, hostname) (libvirt_domain_info_maximum_memory_bytes)',
}

# Host Thanos sorgu sablonlari (recording rule'lardan)
HOST_QUERIES = {
    "cpu_percent": 'safir_host_cpu_usage_percent',
    "memory_percent": 'safir_host_memory_usage_percent',
    "disk_percent": 'safir_host_disk_usage_percent',
    "memory_total": 'node_memory_MemTotal_bytes',
    "disk_total": 'node_filesystem_size_bytes{mountpoint="/"}',
    "nodename": 'node_uname_info',
}

# Placement sorgu sablonlari
PLACEMENT_QUERIES = {
    "vcpu_used": 'openstack_placement_resource_usage{resourcetype="VCPU"}',
    "vcpu_total": 'openstack_placement_resource_total{resourcetype="VCPU"} * on(hostname) group_left openstack_placement_resource_allocation_ratio{resourcetype="VCPU"}',
    "memory_used": 'openstack_placement_resource_usage{resourcetype="MEMORY_MB"}',
    "memory_total": 'openstack_placement_resource_total{resourcetype="MEMORY_MB"} * on(hostname) group_left openstack_placement_resource_allocation_ratio{resourcetype="MEMORY_MB"}',
    "disk_used": 'openstack_placement_resource_usage{resourcetype="DISK_GB"}',
    "disk_total": 'openstack_placement_resource_total{resourcetype="DISK_GB"} * on(hostname) group_left openstack_placement_resource_allocation_ratio{resourcetype="DISK_GB"}',
}


async def query_thanos(session, query, start, end, step="1h", timeout=120):
    """Thanos'a range query gonderir."""
    url = f"{CONF.thanos.querier_endpoint}/api/v1/query_range"
    data = {"query": query, "start": start, "end": end, "step": step}
    try:
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                body = await resp.text()
                LOG.error(f"Thanos error {resp.status}: {body[:200]}")
                return []
            result = await resp.json()
            if result.get("status") != "success":
                LOG.error(f"Thanos query unsuccessful: {result}")
                return []
            return result.get("data", {}).get("result", [])
    except Exception as e:
        LOG.error(f"Thanos query failed: {e}")
        return []


async def fetch_queries(session, queries, start, end, label=""):
    """Sorgu setini paralel olarak Thanos'tan ceker."""
    timeout = CONF.collector.query_timeout
    tasks = {
        name: query_thanos(session, q, start, end, timeout=timeout)
        for name, q in queries.items()
    }
    results = {}
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for name, result in zip(tasks.keys(), gathered):
        if isinstance(result, list):
            results[name] = result
            LOG.info(f"  [{label}] {name}: {len(result)} series")
        else:
            LOG.warning(f"  [{label}] {name}: FAILED - {result}")
            results[name] = []
    return results


def merge_vm_data(results, timestamp):
    """Thanos sonuclarini VM bazinda birlestirir."""
    vm_map = {}
    for metric_name, series_list in results.items():
        for series in series_list:
            labels = series.get("metric", {})
            instance_id = labels.get("instance_id", "")
            if not instance_id:
                continue

            if instance_id not in vm_map:
                vm_map[instance_id] = {
                    "instance_id": instance_id,
                    "instance_name": labels.get("instance_name", "unknown"),
                    "project_id": labels.get("project_id", ""),
                    "hostname": labels.get("hostname", ""),
                    "timestamp": timestamp,
                }

            values = series.get("values", [])
            if not values:
                continue

            # Son degeri al, NaN kontrolu yap
            import math
            val = float(values[-1][1])
            if math.isnan(val) or math.isinf(val):
                continue

            if metric_name == "allocated_memory":
                vm_map[instance_id]["allocated_memory_bytes"] = int(val)
            elif metric_name == "allocated_vcpu":
                vm_map[instance_id]["allocated_vcpu"] = int(val)
            elif metric_name == "disk_io":
                vm_map[instance_id]["disk_io_bytes_sec"] = round(val, 2)
            elif metric_name == "net_io":
                vm_map[instance_id]["net_io_bytes_sec"] = round(val, 2)
            else:
                vm_map[instance_id][metric_name] = round(val, 2)

    return list(vm_map.values())


def get_db_connection():
    """MySQL baglantisi olusturur."""
    conn_str = CONF.database.connection
    # mysql+pymysql://user:pass@host:port/db?charset=utf8 -> parse
    # pymysql dogrudan kullaniyoruz (async degil, collector icin yeterli)
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(conn_str.replace("mysql+pymysql://", "mysql://").replace("mysql+aiomysql://", "mysql://"))
    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/'),
        charset='utf8',
        autocommit=True,
    )


def merge_host_data(host_results, placement_results, timestamp):
    """Thanos sonuclarini host bazinda birlestirir."""
    import math
    host_map = {}

    # Nodename resolve: instance -> nodename
    nodename_map = {}
    for series in host_results.get("nodename", []):
        labels = series.get("metric", {})
        inst = labels.get("instance", "")
        nodename = labels.get("nodename", "")
        if inst and nodename:
            nodename_map[inst] = nodename

    # Host metrikleri
    for metric_name, series_list in host_results.items():
        if metric_name == "nodename":
            continue
        for series in series_list:
            labels = series.get("metric", {})
            instance = labels.get("instance", "")
            if not instance:
                continue

            if instance not in host_map:
                host_map[instance] = {
                    "instance": instance,
                    "nodename": nodename_map.get(instance, ""),
                    "timestamp": timestamp,
                }

            values = series.get("values", [])
            if not values:
                continue
            val = float(values[-1][1])
            if math.isnan(val) or math.isinf(val):
                continue

            if metric_name == "memory_total":
                host_map[instance]["memory_total_bytes"] = int(val)
            elif metric_name == "disk_total":
                host_map[instance]["disk_total_bytes"] = int(val)
            else:
                host_map[instance][metric_name] = round(val, 2)

    # Placement metrikleri (hostname bazli — nodename ile eslestir)
    # nodename -> instance reverse map
    reverse_map = {v: k for k, v in nodename_map.items()}

    for metric_name, series_list in placement_results.items():
        for series in series_list:
            labels = series.get("metric", {})
            hostname = labels.get("hostname", "")
            if not hostname:
                continue

            # hostname'den instance bul (kisa hostname ile de esles)
            instance = reverse_map.get(hostname, "")
            if not instance:
                # FQDN olabilir, kisa isimle dene
                short = hostname.split(".")[0]
                instance = reverse_map.get(short, "")
            if not instance:
                # Yeni bir host olarak ekle
                instance = hostname
                if instance not in host_map:
                    host_map[instance] = {
                        "instance": instance,
                        "nodename": hostname,
                        "timestamp": timestamp,
                    }

            values = series.get("values", [])
            if not values:
                continue
            val = float(values[-1][1])
            if math.isnan(val) or math.isinf(val):
                continue

            field_map = {
                "vcpu_used": "placement_vcpu_used",
                "vcpu_total": "placement_vcpu_total",
                "memory_used": "placement_memory_used_mb",
                "memory_total": "placement_memory_total_mb",
                "disk_used": "placement_disk_used_gb",
                "disk_total": "placement_disk_total_gb",
            }
            field = field_map.get(metric_name)
            if field:
                host_map[instance][field] = round(val, 2)

    return list(host_map.values())


def insert_vm_metrics(conn, vm_list):
    """VM metriklerini vm_metrics_hourly tablosuna bulk insert yapar."""
    if not vm_list:
        return 0

    sql = """
        INSERT INTO vm_metrics_hourly
        (instance_id, instance_name, project_id, hostname, timestamp,
         avg_cpu, max_cpu, avg_memory, max_memory,
         disk_io_bytes_sec, net_io_bytes_sec,
         allocated_vcpu, allocated_memory_bytes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            instance_name = VALUES(instance_name),
            project_id = VALUES(project_id),
            hostname = VALUES(hostname),
            avg_cpu = VALUES(avg_cpu),
            max_cpu = VALUES(max_cpu),
            avg_memory = VALUES(avg_memory),
            max_memory = VALUES(max_memory),
            disk_io_bytes_sec = VALUES(disk_io_bytes_sec),
            net_io_bytes_sec = VALUES(net_io_bytes_sec),
            allocated_vcpu = VALUES(allocated_vcpu),
            allocated_memory_bytes = VALUES(allocated_memory_bytes)
    """

    rows = []
    for vm in vm_list:
        rows.append((
            vm["instance_id"],
            vm.get("instance_name"),
            vm.get("project_id"),
            vm.get("hostname"),
            vm["timestamp"],
            vm.get("avg_cpu"),
            vm.get("max_cpu"),
            vm.get("avg_memory"),
            vm.get("max_memory"),
            vm.get("disk_io_bytes_sec"),
            vm.get("net_io_bytes_sec"),
            vm.get("allocated_vcpu"),
            vm.get("allocated_memory_bytes"),
        ))

    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)

    LOG.info(f"Inserted {len(rows)} rows into vm_metrics_hourly")
    return len(rows)


def insert_host_metrics(conn, host_list):
    """Host metriklerini host_metrics_hourly tablosuna bulk insert yapar."""
    if not host_list:
        return 0

    sql = """
        INSERT INTO host_metrics_hourly
        (instance, nodename, timestamp,
         cpu_percent, memory_percent, disk_percent,
         memory_total_bytes, disk_total_bytes,
         placement_vcpu_used, placement_vcpu_total,
         placement_memory_used_mb, placement_memory_total_mb,
         placement_disk_used_gb, placement_disk_total_gb)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            nodename = VALUES(nodename),
            cpu_percent = VALUES(cpu_percent),
            memory_percent = VALUES(memory_percent),
            disk_percent = VALUES(disk_percent),
            memory_total_bytes = VALUES(memory_total_bytes),
            disk_total_bytes = VALUES(disk_total_bytes),
            placement_vcpu_used = VALUES(placement_vcpu_used),
            placement_vcpu_total = VALUES(placement_vcpu_total),
            placement_memory_used_mb = VALUES(placement_memory_used_mb),
            placement_memory_total_mb = VALUES(placement_memory_total_mb),
            placement_disk_used_gb = VALUES(placement_disk_used_gb),
            placement_disk_total_gb = VALUES(placement_disk_total_gb)
    """

    rows = []
    for h in host_list:
        rows.append((
            h["instance"],
            h.get("nodename"),
            h["timestamp"],
            h.get("cpu_percent"),
            h.get("memory_percent"),
            h.get("disk_percent"),
            h.get("memory_total_bytes"),
            h.get("disk_total_bytes"),
            h.get("placement_vcpu_used"),
            h.get("placement_vcpu_total"),
            h.get("placement_memory_used_mb"),
            h.get("placement_memory_total_mb"),
            h.get("placement_disk_used_gb"),
            h.get("placement_disk_total_gb"),
        ))

    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)

    LOG.info(f"Inserted {len(rows)} rows into host_metrics_hourly")
    return len(rows)


def cleanup_old_data(conn, retention_days):
    """Eski verileri siler."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    total_deleted = 0
    with conn.cursor() as cursor:
        for table in ["vm_metrics_hourly", "host_metrics_hourly"]:
            cursor.execute(f"DELETE FROM {table} WHERE timestamp < %s", (cutoff,))
            deleted = cursor.rowcount
            if deleted:
                LOG.info(f"Cleaned up {deleted} rows from {table} older than {retention_days} days")
            total_deleted += deleted
    return total_deleted


async def run_collection():
    """Ana collection dongusu."""
    now = datetime.now()
    end_unix = int(now.timestamp())
    start_unix = int((now - timedelta(hours=1)).timestamp())
    timestamp = now.replace(minute=0, second=0, microsecond=0)

    LOG.info(f"Starting metrics collection: {timestamp}")
    LOG.info(f"Thanos endpoint: {CONF.thanos.querier_endpoint}")

    async with aiohttp.ClientSession() as session:
        # 1. VM + Host + Placement sorgularini paralel cek
        vm_results = await fetch_queries(session, VM_QUERIES, start_unix, end_unix, label="VM")
        host_results = await fetch_queries(session, HOST_QUERIES, start_unix, end_unix, label="HOST")
        placement_results = await fetch_queries(session, PLACEMENT_QUERIES, start_unix, end_unix, label="PLACEMENT")

    # 2. Birlestir
    vm_list = merge_vm_data(vm_results, timestamp)
    host_list = merge_host_data(host_results, placement_results, timestamp)
    LOG.info(f"Merged {len(vm_list)} VMs, {len(host_list)} hosts")

    # 3. MySQL'e yaz
    conn = get_db_connection()
    try:
        insert_vm_metrics(conn, vm_list)
        insert_host_metrics(conn, host_list)
        cleanup_old_data(conn, CONF.collector.retention_days)
    finally:
        conn.close()

    LOG.info(f"Collection complete: {len(vm_list)} VMs, {len(host_list)} hosts")


def main():
    """Entry point."""
    # Config dosyasini oku
    config_file = None
    for i, arg in enumerate(sys.argv):
        if arg == '--config-file' and i + 1 < len(sys.argv):
            config_file = sys.argv[i + 1]
            break

    if not config_file:
        # Varsayilan config yollarini dene
        for path in ['/etc/safirmonitoring/safirmonitoring.conf',
                     '/etc/safir_monitoring/safir_monitoring.conf']:
            if os.path.exists(path):
                config_file = path
                break

    if not config_file:
        print("ERROR: Config file not found. Use --config-file <path>")
        sys.exit(1)

    logging.register_options(CONF)
    logging.set_defaults()
    CONF(['--config-file', config_file], project='safir_monitoring')
    logging.setup(CONF, 'safir_monitoring_collector')

    LOG.info("=" * 60)
    LOG.info("VM Metrics Collector starting")
    LOG.info("=" * 60)

    try:
        asyncio.run(run_collection())
    except Exception as e:
        LOG.error(f"Collection failed: {e}", exc_info=True)
        sys.exit(1)

    LOG.info("VM Metrics Collector finished successfully")


if __name__ == '__main__':
    main()
