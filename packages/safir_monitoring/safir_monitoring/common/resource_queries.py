"""Resource type -> PromQL sorgu eslestirmesi.

Forecasting ve rightsizing endpoint'leri bu config'i kullanir.
metric_source: real (node-exporter) veya placement (openstack-exporter)

Host metrikleri Thanos recording rule'lardan gelir (safir_ prefix'li):
  - safir_host_cpu_usage_percent
  - safir_host_memory_usage_percent
  - safir_host_disk_usage_percent

VM CPU metrigi de recording rule'dan gelir:
  - libvirt_domain_cpu_utilization_perc
"""

VALID_RESOURCE_TYPES = {"cpu", "memory", "disk"}
VALID_METRIC_SOURCES = {"real", "placement"}

# Placement resourcetype eslestirmesi
_PLACEMENT_RESOURCE_TYPES = {
    "cpu": "VCPU",
    "memory": "MEMORY_MB",
    "disk": "DISK_GB",
}

# Recording rule metrik isimleri (rate() onceden hesaplanmis)
_HOST_RECORDING_RULES = {
    "cpu": "safir_host_cpu_usage_percent",
    "memory": "safir_host_memory_usage_percent",
    "disk": "safir_host_disk_usage_percent",
}


def _labels(fixed: str = None, instance: str = None) -> str:
    """PromQL label filtresi olusturur. Bos ise {} bile koymaz."""
    parts = []
    if fixed:
        parts.append(fixed)
    if instance:
        parts.append(f'instance="{instance}"')
    return "{" + ",".join(parts) + "}" if parts else ""


def _placement_labels(resource_type: str, hostname: str = None) -> str:
    """Placement metrikleri icin label filtresi.

    hostname regex match kullanir: 'test-compute1' -> hostname=~'test-compute1.*'
    Bu sayede FQDN (test-compute1.openstack.local) ile de eslesir.
    """
    rt = _PLACEMENT_RESOURCE_TYPES[resource_type]
    parts = [f'resourcetype="{rt}"']
    if hostname:
        if "." not in hostname:
            parts.append(f'hostname=~"{hostname}.*"')
        else:
            parts.append(f'hostname="{hostname}"')
    return "{" + ",".join(parts) + "}"


# ============================================================================
# REAL USAGE (recording rules — rate() onceden hesaplanmis)
# ============================================================================

def build_host_query(resource_type: str, instance: str = None) -> str:
    """Host icin PromQL sorgusu olusturur (yuzde cinsinden).

    Thanos recording rule'lardan onceden hesaplanmis metrikleri kullanir.
    rate() hesaplamasi yok — dogrudan deger cekilir.
    """
    metric = _HOST_RECORDING_RULES[resource_type]
    lbl = _labels(instance=instance)
    return f'{metric}{lbl}'


def build_host_capacity_query(resource_type: str, instance: str = None):
    """Host kapasite sorgusu. Sabit deger veya PromQL doner."""
    if resource_type == "cpu":
        return 100  # Yuzde
    elif resource_type == "memory":
        lbl = _labels(instance=instance)
        return f'node_memory_MemTotal_bytes{lbl}'
    elif resource_type == "disk":
        lbl = _labels('mountpoint="/"', instance)
        return f'node_filesystem_size_bytes{lbl}'
    raise ValueError(f"Invalid resource_type: {resource_type}")


# ============================================================================
# PLACEMENT (openstack-exporter)
# ============================================================================

def build_placement_query(resource_type: str, hostname: str = None) -> str:
    """Placement bazli ham usage sorgusu.

    Yuzde hesabi Python tarafinda yapilir (usage / capacity * 100).
    Memory: MB -> GB donusumu yapilir (capacity ile ayni birim).
    """
    lbl = _placement_labels(resource_type, hostname)
    if hostname:
        base = f'openstack_placement_resource_usage{lbl}'
    else:
        rt = _PLACEMENT_RESOURCE_TYPES[resource_type]
        base = f'sum(openstack_placement_resource_usage{{resourcetype="{rt}"}})'

    # Memory MB -> GB (capacity ile ayni birim)
    if resource_type == "memory":
        return f'{base} / 1024'
    return base


def build_placement_capacity_query(resource_type: str, hostname: str = None):
    """Placement bazli toplam kapasite sorgusu (overcommit dahil)."""
    lbl = _placement_labels(resource_type, hostname)
    total = f'openstack_placement_resource_total{lbl}'
    ratio = f'openstack_placement_resource_allocation_ratio{lbl}'

    if hostname:
        base = f'{total} * {ratio}'
    else:
        rt = _PLACEMENT_RESOURCE_TYPES[resource_type]
        rt_lbl = f'{{resourcetype="{rt}"}}'
        base = (
            f'sum(openstack_placement_resource_total{rt_lbl} * on(hostname) group_left '
            f'openstack_placement_resource_allocation_ratio{rt_lbl})'
        )

    # Memory MB -> GB donusumu
    if resource_type == "memory":
        return f'{base} / 1024'
    return base


# ============================================================================
# VM (libvirt-exporter + recording rules)
# ============================================================================

def build_vm_query(resource_type: str, project_id: str = None, instance_id: str = None) -> str:
    """VM icin PromQL sorgusu olusturur (yuzde cinsinden).

    CPU: libvirt_domain_cpu_utilization_perc recording rule'dan gelir.
    """
    parts = []
    if project_id:
        parts.append(f'project_id="{project_id}"')
    if instance_id:
        parts.append(f'instance_id="{instance_id}"')
    lbl = "{" + ",".join(parts) + "}" if parts else ""

    if resource_type == "cpu":
        return f'libvirt_domain_cpu_utilization_perc{lbl}'
    elif resource_type == "memory":
        return f'libvirt_domain_memory_stats_used_percent{lbl}'
    elif resource_type == "disk":
        return f'libvirt_domain_block_stats_allocation_bytes{lbl} / libvirt_domain_block_stats_capacity_bytes{lbl} * 100'
    raise ValueError(f"Invalid resource_type: {resource_type}")
