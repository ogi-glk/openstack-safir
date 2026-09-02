# Safir Monitoring - Metrik Katalogu

Bu dokuman, safir_monitoring servisinin `/api/v1/metrics/names` endpoint'inden donen metrikleri kategorize eder.

---

## 1. Libvirt (VM) Metrikleri

VM'lerin kaynak kullanimini izlemek icin kullanilir. Tum libvirt metrikleri asagidaki ortak dimension'lara sahiptir:

### Ortak Dimension'lar

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `hostname` | Compute host adi | `test-compute1.openstack.local` |
| `instance_name` | VM adi | `web-server-1` |
| `instance_id` | OpenStack instance UUID | `abc-123-def` |
| `project_id` | OpenStack proje UUID | `99fe423d-...` |
| `instance` | Exporter adresi | `10.0.0.1:9177` |
| `job` | Prometheus job adi | `libvirt-exporter` |

### 1.1 CPU

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_cpu_utilization_perc` | VM CPU kullanim yuzdesi | % |
| `libvirt_domain_info_cpu_time_seconds_total` | Toplam CPU suresi (counter) | saniye |
| `libvirt_domain_info_virtual_cpus` | Atanan vCPU sayisi | adet |
| `libvirt_domain_vcpu_current` | Aktif vCPU sayisi | adet |
| `libvirt_domain_vcpu_maximum` | Maksimum vCPU sayisi | adet |
| `libvirt_domain_vcpu_time_seconds_total` | vCPU basina toplam CPU suresi | saniye |
| `libvirt_domain_vcpu_delay_seconds_total` | vCPU zamanlama gecikmesi | saniye |
| `libvirt_domain_vcpu_wait_seconds_total` | vCPU bekleme suresi | saniye |
| `libvirt_domain_vcpu_state` | vCPU durumu (0=offline, 1=running, 2=blocked) | enum |

**Ek dimension'lar:**

| Dimension | Aciklama | Gecerli Metrikler |
|-----------|----------|-------------------|
| `vcpu` | vCPU indeksi (0, 1, 2, ...) | `vcpu_time`, `vcpu_delay`, `vcpu_wait`, `vcpu_state` |

### 1.2 Memory

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_info_maximum_memory_bytes` | VM'e atanan maksimum bellek | byte |
| `libvirt_domain_info_memory_usage_bytes` | Kullanilan bellek | byte |
| `libvirt_domain_memory_stats_used_percent` | Bellek kullanim yuzdesi | % |
| `libvirt_domain_memory_stats_available_bytes` | Kullanilabilir bellek | byte |
| `libvirt_domain_memory_stats_unused_bytes` | Kullanilmayan bellek | byte |
| `libvirt_domain_memory_stats_usable_bytes` | Tahsis edilebilir bellek | byte |
| `libvirt_domain_memory_stats_maximum_bytes` | Maksimum bellek (balon) | byte |
| `libvirt_domain_memory_stats_rss_bytes` | Host uzerindeki RSS | byte |
| `libvirt_domain_memory_stats_current_balloon_bytes` | Mevcut balon boyutu | byte |
| `libvirt_domain_memory_stats_disk_caches_bytes` | Disk cache boyutu | byte |
| `libvirt_domain_memory_stats_swap_in_bytes` | Swap'a yazilan | byte |
| `libvirt_domain_memory_stats_swap_out_bytes` | Swap'tan okunan | byte |
| `libvirt_domain_memory_stats_major_fault_total` | Major page fault sayisi (counter) | adet |
| `libvirt_domain_memory_stats_minor_fault_total` | Minor page fault sayisi (counter) | adet |
| `libvirt_domain_memory_stats_hugetlb_pgalloc_total` | HugePage tahsis sayisi (counter) | adet |
| `libvirt_domain_memory_stats_hugetlb_pgfail_total` | HugePage hata sayisi (counter) | adet |
| `libvirt_domain_memory_stats_last_update_timestamp_seconds` | Son guncelleme zamani | unix timestamp |

### 1.3 Disk (Block I/O)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_block_stats_read_bytes_total` | Okunan toplam byte (counter) | byte |
| `libvirt_domain_block_stats_write_bytes_total` | Yazilan toplam byte (counter) | byte |
| `libvirt_domain_block_stats_read_requests_total` | Okuma istegi sayisi (counter) | adet |
| `libvirt_domain_block_stats_write_requests_total` | Yazma istegi sayisi (counter) | adet |
| `libvirt_domain_block_stats_read_time_seconds_total` | Okuma suresi (counter) | saniye |
| `libvirt_domain_block_stats_write_time_seconds_total` | Yazma suresi (counter) | saniye |
| `libvirt_domain_block_stats_flush_requests_total` | Flush istegi sayisi (counter) | adet |
| `libvirt_domain_block_stats_flush_time_seconds_total` | Flush suresi (counter) | saniye |
| `libvirt_domain_block_stats_capacity_bytes` | Disk kapasitesi | byte |
| `libvirt_domain_block_stats_allocation_bytes` | Tahsis edilen disk alani | byte |
| `libvirt_domain_block_stats_physical_bytes` | Fiziksel disk boyutu | byte |
| `libvirt_domain_block_stats_info` | Disk bilgisi (meta) | info |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `target_device` | Disk aygit adi | `vda`, `vdb` |
| `bus` | Bus tipi | `virtio`, `ide` |
| `serial` | Disk seri numarasi | `volume-abc-123` |
| `source_file` | Kaynak dosya/volume yolu | `/dev/ceph/volume-...` |

### 1.4 Network (Interface I/O)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_interface_stats_receive_bytes_total` | Alinan toplam byte (counter) | byte |
| `libvirt_domain_interface_stats_transmit_bytes_total` | Gonderilen toplam byte (counter) | byte |
| `libvirt_domain_interface_stats_receive_packets_total` | Alinan paket sayisi (counter) | adet |
| `libvirt_domain_interface_stats_transmit_packets_total` | Gonderilen paket sayisi (counter) | adet |
| `libvirt_domain_interface_stats_receive_errors_total` | Alma hatalari (counter) | adet |
| `libvirt_domain_interface_stats_transmit_errors_total` | Gonderme hatalari (counter) | adet |
| `libvirt_domain_interface_stats_receive_drops_total` | Dusurulmus gelen paketler (counter) | adet |
| `libvirt_domain_interface_stats_transmit_drops_total` | Dusurulmus giden paketler (counter) | adet |
| `libvirt_domain_interface_stats_info` | Arayuz bilgisi (meta) | info |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `target_device` | Arayuz adi (host tarafinda) | `tapXXXXXX` |
| `source_bridge` | Kaynak bridge | `br-int` |
| `mac_address` | MAC adresi | `fa:16:3e:xx:xx:xx` |

### 1.5 Migration (Job Info)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_job_info_type` | Migration is tipi (0=none, 1=unbounded, 2=bounded, 3=completed) | enum |
| `libvirt_domain_job_info_time_elapsed_seconds` | Gecen sure | saniye |
| `libvirt_domain_job_info_time_remaining_seconds` | Kalan tahmini sure | saniye |
| `libvirt_domain_job_info_data_total_bytes` | Toplam aktarilacak veri | byte |
| `libvirt_domain_job_info_data_processed_bytes` | Islenen veri | byte |
| `libvirt_domain_job_info_data_remaining_bytes` | Kalan veri | byte |
| `libvirt_domain_job_info_memory_total_bytes` | Toplam bellek verisi | byte |
| `libvirt_domain_job_info_memory_processed_bytes` | Islenen bellek | byte |
| `libvirt_domain_job_info_memory_remaining_bytes` | Kalan bellek | byte |
| `libvirt_domain_job_info_file_total_bytes` | Toplam dosya verisi | byte |
| `libvirt_domain_job_info_file_processed_bytes` | Islenen dosya | byte |
| `libvirt_domain_job_info_file_remaining_bytes` | Kalan dosya | byte |

### 1.6 Genel / Meta

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `libvirt_domain_info` | VM durum bilgisi (meta) | info |
| `libvirt_domain_info_state` | VM durumu (1=running, 3=paused, 5=shutoff, ...) | enum |
| `libvirt_domain_openstack_info` | OpenStack meta verisi (flavor, tenant, ...) | info |
| `libvirt_domain_timed_out` | Exporter sorgusu timeout oldu mu | bool (0/1) |
| `libvirt_domains` | Toplam VM sayisi (host basina) | adet |
| `libvirt_up` | Exporter durumu | bool (0/1) |

---

## 2. Node (Host) Metrikleri

Fiziksel sunucularin kaynak kullanimini izlemek icin kullanilir.

### Ortak Dimension'lar

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `instance` | Exporter adresi | `10.0.0.1:9100` |
| `job` | Prometheus job adi | `node-exporter` |
| `nodename` | Host adi (`node_uname_info` join ile) | `compute-01` |

### 2.1 CPU

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_cpu_seconds_total` | CPU modu basina gecen sure (counter) | saniye |
| `node_cpu_guest_seconds_total` | Guest (VM) icin harcanan CPU (counter) | saniye |
| `node_cpu_frequency_max_hertz` | Maksimum CPU frekansi | Hz |
| `node_cpu_frequency_min_hertz` | Minimum CPU frekansi | Hz |
| `node_cpu_scaling_frequency_hertz` | Anlik CPU frekansi | Hz |
| `node_cpu_scaling_frequency_max_hertz` | Scaling max frekans | Hz |
| `node_cpu_scaling_frequency_min_hertz` | Scaling min frekans | Hz |
| `node_cpu_scaling_governor` | CPU governor modu | info |
| `node_cpu_core_throttles_total` | Core throttle sayisi (counter) | adet |
| `node_cpu_package_throttles_total` | Package throttle sayisi (counter) | adet |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `cpu` | CPU cekirdek indeksi | `0`, `1`, `2` |
| `mode` | CPU modu | `idle`, `user`, `system`, `iowait`, `steal`, `nice`, `irq`, `softirq` |

### 2.2 Memory

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_memory_MemTotal_bytes` | Toplam fiziksel bellek | byte |
| `node_memory_MemFree_bytes` | Bos bellek | byte |
| `node_memory_MemAvailable_bytes` | Kullanilabilir bellek | byte |
| `node_memory_Buffers_bytes` | Buffer cache | byte |
| `node_memory_Cached_bytes` | Page cache | byte |
| `node_memory_SwapTotal_bytes` | Toplam swap | byte |
| `node_memory_SwapFree_bytes` | Bos swap | byte |
| `node_memory_SwapCached_bytes` | Swap cache | byte |
| `node_memory_Active_bytes` | Aktif bellek | byte |
| `node_memory_Inactive_bytes` | Inaktif bellek | byte |
| `node_memory_Slab_bytes` | Kernel slab | byte |
| `node_memory_Mapped_bytes` | Mapped bellek | byte |
| `node_memory_Dirty_bytes` | Dirty page'ler | byte |
| `node_memory_Writeback_bytes` | Writeback sureci | byte |
| `node_memory_HugePages_Total` | Toplam hugepage | adet |
| `node_memory_HugePages_Free` | Bos hugepage | adet |
| `node_memory_Hugepagesize_bytes` | Hugepage boyutu | byte |
| `node_memory_CommitLimit_bytes` | Commit limiti | byte |
| `node_memory_Committed_AS_bytes` | Committed bellek | byte |
| `node_memory_VmallocTotal_bytes` | Vmalloc toplam | byte |
| `node_memory_VmallocUsed_bytes` | Vmalloc kullanilan | byte |
| `node_memory_KernelStack_bytes` | Kernel stack | byte |
| `node_memory_PageTables_bytes` | Page table boyutu | byte |

### 2.3 Disk / Filesystem

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_filesystem_size_bytes` | Dosya sistemi toplam boyutu | byte |
| `node_filesystem_free_bytes` | Bos alan | byte |
| `node_filesystem_avail_bytes` | Kullanilabilir alan (non-root) | byte |
| `node_filesystem_files` | Toplam inode sayisi | adet |
| `node_filesystem_files_free` | Bos inode sayisi | adet |
| `node_filesystem_readonly` | Salt okunur mu | bool (0/1) |
| `node_filesystem_device_error` | Aygit hatasi var mi | bool (0/1) |
| `node_disk_read_bytes_total` | Okunan toplam byte (counter) | byte |
| `node_disk_written_bytes_total` | Yazilan toplam byte (counter) | byte |
| `node_disk_reads_completed_total` | Tamamlanan okuma (counter) | adet |
| `node_disk_writes_completed_total` | Tamamlanan yazma (counter) | adet |
| `node_disk_read_time_seconds_total` | Okuma suresi (counter) | saniye |
| `node_disk_write_time_seconds_total` | Yazma suresi (counter) | saniye |
| `node_disk_io_now` | Anlik I/O islem sayisi | adet |
| `node_disk_io_time_seconds_total` | Toplam I/O suresi (counter) | saniye |
| `node_disk_io_time_weighted_seconds_total` | Agirlikli I/O suresi (counter) | saniye |
| `node_disk_info` | Disk bilgisi (meta) | info |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `device` | Disk aygit adi | `sda`, `nvme0n1`, `dm-0` |
| `mountpoint` | Baglama noktasi | `/`, `/var`, `/home` |
| `fstype` | Dosya sistemi tipi | `ext4`, `xfs`, `zfs` |

### 2.4 Network

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_network_receive_bytes_total` | Alinan toplam byte (counter) | byte |
| `node_network_transmit_bytes_total` | Gonderilen toplam byte (counter) | byte |
| `node_network_receive_packets_total` | Alinan paket (counter) | adet |
| `node_network_transmit_packets_total` | Gonderilen paket (counter) | adet |
| `node_network_receive_errs_total` | Alma hatalari (counter) | adet |
| `node_network_transmit_errs_total` | Gonderme hatalari (counter) | adet |
| `node_network_receive_drop_total` | Dusurulmus gelen (counter) | adet |
| `node_network_transmit_drop_total` | Dusurulmus giden (counter) | adet |
| `node_network_speed_bytes` | Arayuz hizi | byte/s |
| `node_network_mtu_bytes` | MTU | byte |
| `node_network_up` | Arayuz durumu | bool (0/1) |
| `node_network_carrier` | Carrier durumu | bool (0/1) |
| `node_network_info` | Arayuz bilgisi (meta) | info |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `device` | Arayuz adi | `eth0`, `bond0`, `br-ex` |

### 2.5 System / Load

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_load1` | 1 dakikalik load average | ratio |
| `node_load5` | 5 dakikalik load average | ratio |
| `node_load15` | 15 dakikalik load average | ratio |
| `node_procs_running` | Calisan proses sayisi | adet |
| `node_procs_blocked` | Bloke proses sayisi | adet |
| `node_boot_time_seconds` | Son boot zamani | unix timestamp |
| `node_context_switches_total` | Context switch sayisi (counter) | adet |
| `node_forks_total` | Fork sayisi (counter) | adet |
| `node_intr_total` | Interrupt sayisi (counter) | adet |
| `node_entropy_available_bits` | Mevcut entropi | bit |
| `node_filefd_allocated` | Acik dosya tanimlayici | adet |
| `node_filefd_maximum` | Maksimum dosya tanimlayici | adet |
| `node_uname_info` | Host bilgisi (meta) | info |
| `node_os_info` | OS bilgisi (meta) | info |
| `node_dmi_info` | Donanim bilgisi (meta) | info |
| `node_exporter_build_info` | Exporter versiyon bilgisi | info |

### 2.6 Systemd

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_systemd_unit_state` | Servis durumu | enum |
| `node_systemd_units` | Toplam unit sayisi | adet |
| `node_systemd_system_running` | Sistem calisiyor mu | bool (0/1) |
| `node_systemd_timer_last_trigger_seconds` | Timer son tetiklenme | unix timestamp |
| `node_systemd_version` | Systemd versiyonu | info |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `name` | Unit adi | `sshd.service`, `docker.service` |
| `state` | Unit durumu | `active`, `inactive`, `failed` |
| `type` | Unit tipi | `service`, `socket`, `timer` |

### 2.7 TCP/Network Stack

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_tcp_connection_states` | TCP baglanti durumu basina sayi | adet |
| `node_sockstat_TCP_inuse` | Kullanilan TCP soket | adet |
| `node_sockstat_TCP_alloc` | Tahsis edilen TCP soket | adet |
| `node_sockstat_TCP_tw` | TIME_WAIT soket | adet |
| `node_sockstat_UDP_inuse` | Kullanilan UDP soket | adet |
| `node_sockstat_sockets_used` | Toplam kullanilan soket | adet |
| `node_netstat_Tcp_CurrEstab` | Aktif TCP baglanti | adet |
| `node_netstat_Tcp_ActiveOpens` | Acilan TCP baglanti (counter) | adet |
| `node_netstat_Tcp_RetransSegs` | Retransmit (counter) | adet |
| `node_nf_conntrack_entries` | Conntrack girisi | adet |
| `node_nf_conntrack_entries_limit` | Conntrack limiti | adet |

**Ek dimension'lar (tcp_connection_states):**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `state` | TCP durumu | `established`, `time_wait`, `close_wait`, `listen` |

### 2.8 Hardware / Thermal

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_hwmon_temp_celsius` | Sensor sicakligi | C |
| `node_hwmon_temp_crit_celsius` | Kritik sicaklik esigi | C |
| `node_hwmon_temp_max_celsius` | Maksimum sicaklik esigi | C |
| `node_hwmon_power_average_watt` | Ortalama guc tuketimi | W |
| `node_thermal_zone_temp` | Thermal zone sicakligi | C |
| `node_rapl_package_joules_total` | CPU paket enerji tuketimi (counter) | J |
| `node_rapl_dram_joules_total` | DRAM enerji tuketimi (counter) | J |
| `node_cooling_device_cur_state` | Sogutma cihazi mevcut durumu | enum |
| `node_cooling_device_max_state` | Sogutma cihazi maks durumu | enum |

### 2.9 ZFS (varsa)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_zfs_arc_size` | ARC boyutu | byte |
| `node_zfs_arc_hits` | ARC hit sayisi | adet |
| `node_zfs_arc_misses` | ARC miss sayisi | adet |
| `node_zfs_arc_c_max` | ARC maksimum boyutu | byte |

> ZFS metrikleri sadece ZFS kullanilan host'larda mevcuttur. `node_zfs_` prefix'li cok sayida detay metrigi vardir; yukaridaki tablo en onemli olanlari listeler.

### 2.10 InfiniBand (varsa)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_infiniband_port_data_received_bytes_total` | Alinan veri (counter) | byte |
| `node_infiniband_port_data_transmitted_bytes_total` | Gonderilen veri (counter) | byte |
| `node_infiniband_rate_bytes_per_second` | Port hizi | byte/s |
| `node_infiniband_state_id` | Port durumu | enum |

> InfiniBand metrikleri sadece IB donanimli host'larda mevcuttur.

### 2.11 NFS (varsa)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_nfs_requests_total` | NFS istek sayisi (counter) | adet |
| `node_nfs_connections_total` | NFS baglanti sayisi (counter) | adet |
| `node_nfsd_server_rpcs_total` | NFS server RPC sayisi (counter) | adet |
| `node_nfsd_disk_bytes_read_total` | NFS okunan byte (counter) | byte |
| `node_nfsd_disk_bytes_written_total` | NFS yazilan byte (counter) | byte |

### 2.12 Pressure (PSI)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_pressure_cpu_waiting_seconds_total` | CPU baskisi bekleme suresi (counter) | saniye |
| `node_pressure_io_waiting_seconds_total` | I/O baskisi bekleme suresi (counter) | saniye |
| `node_pressure_io_stalled_seconds_total` | I/O durma suresi (counter) | saniye |
| `node_pressure_memory_waiting_seconds_total` | Bellek baskisi bekleme suresi (counter) | saniye |
| `node_pressure_memory_stalled_seconds_total` | Bellek durma suresi (counter) | saniye |

### 2.13 Bonding

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `node_bonding_active` | Aktif bond arayuz sayisi | adet |
| `node_bonding_slaves` | Toplam slave sayisi | adet |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `master` | Bond arayuz adi | `bond0` |

---

## 3. LXC Metrikleri

LXC container durumunu izlemek icin kullanilir.

### Ortak Dimension'lar

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `instance` | Exporter adresi | `10.0.0.1:9100` |
| `job` | Prometheus job adi | `lxc-exporter` |

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `lxc_service_active` | LXC servisi aktif mi | bool (0/1) |

---

## 4. OpenStack Metrikleri

OpenStack servislerinin durumunu ve kaynak kullanimini izlemek icin kullanilir.

### Ortak Dimension'lar

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `instance` | Exporter adresi | `10.0.0.1:9183` |
| `job` | Prometheus job adi | `openstack-exporter` |

### 4.1 Nova (Compute)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_nova_up` | Nova API erisilebilir mi | bool (0/1) |
| `openstack_nova_total_vms` | Toplam VM sayisi | adet |
| `openstack_nova_agent_state` | Nova agent durumu | bool (0/1) |
| `openstack_nova_availability_zones` | Availability zone sayisi | adet |
| `openstack_nova_flavors` | Flavor sayisi | adet |
| `openstack_nova_flavor` | Flavor detaylari (meta) | info |
| `openstack_nova_server_status` | VM durumu | enum |
| `openstack_nova_server_local_gb` | VM lokal disk boyutu | GB |
| `openstack_nova_limits_vcpus_max` | Proje vCPU limiti | adet |
| `openstack_nova_limits_vcpus_used` | Proje kullanilan vCPU | adet |
| `openstack_nova_limits_memory_max` | Proje bellek limiti | MB |
| `openstack_nova_limits_memory_used` | Proje kullanilan bellek | MB |
| `openstack_nova_limits_instances_max` | Proje instance limiti | adet |
| `openstack_nova_limits_instances_used` | Proje kullanilan instance | adet |

**Ek dimension'lar:**

| Dimension | Aciklama | Gecerli Metrikler |
|-----------|----------|-------------------|
| `hostname` | Compute host adi | `agent_state` |
| `service` | Servis adi | `agent_state` |
| `adminState` | Admin durumu | `agent_state` |
| `zone` | AZ | `agent_state` |
| `tenant_id` | Proje UUID | `limits_*`, `server_*`, `quota_*` |
| `id` | VM/flavor UUID | `server_status`, `flavor` |
| `name` | VM/flavor adi | `server_status`, `flavor` |
| `status` | VM durumu (ACTIVE, SHUTOFF, ...) | `server_status` |

### 4.2 Neutron (Network)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_neutron_up` | Neutron API erisilebilir mi | bool (0/1) |
| `openstack_neutron_agent_state` | Neutron agent durumu | bool (0/1) |
| `openstack_neutron_networks` | Toplam ag sayisi | adet |
| `openstack_neutron_subnets` | Toplam subnet sayisi | adet |
| `openstack_neutron_ports` | Toplam port sayisi | adet |
| `openstack_neutron_routers` | Toplam router sayisi | adet |
| `openstack_neutron_floating_ips` | Toplam floating IP sayisi | adet |
| `openstack_neutron_security_groups` | Toplam security group sayisi | adet |
| `openstack_neutron_routers_not_active` | Aktif olmayan router'lar | adet |
| `openstack_neutron_ports_no_ips` | IP'siz portlar | adet |
| `openstack_neutron_floating_ips_associated_not_active` | Aktif olmayan atanmis floating IP | adet |
| `openstack_neutron_network_ip_availabilities_total` | Toplam IP kapasitesi | adet |
| `openstack_neutron_network_ip_availabilities_used` | Kullanilan IP | adet |

**Ek dimension'lar:**

| Dimension | Aciklama | Gecerli Metrikler |
|-----------|----------|-------------------|
| `tenant_id` | Proje UUID | `network`, `subnet`, `port`, `router`, `floating_ip` |
| `network_id` | Ag UUID | `ip_availabilities_*` |
| `subnet_name` | Subnet adi | `ip_availabilities_*` |

### 4.3 Cinder (Block Storage)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_cinder_up` | Cinder API erisilebilir mi | bool (0/1) |
| `openstack_cinder_agent_state` | Cinder agent durumu | bool (0/1) |
| `openstack_cinder_volumes` | Toplam volume sayisi | adet |
| `openstack_cinder_snapshots` | Toplam snapshot sayisi | adet |
| `openstack_cinder_volume_gb` | Volume boyutu | GB |
| `openstack_cinder_volume_status` | Volume durumu | enum |
| `openstack_cinder_pool_capacity_total_gb` | Pool toplam kapasite | GB |
| `openstack_cinder_pool_capacity_free_gb` | Pool bos kapasite | GB |
| `openstack_cinder_limits_volume_max_gb` | Proje volume limiti | GB |
| `openstack_cinder_limits_volume_used_gb` | Proje kullanilan volume | GB |
| `openstack_cinder_limits_backup_max_gb` | Proje backup limiti | GB |
| `openstack_cinder_limits_backup_used_gb` | Proje kullanilan backup | GB |

### 4.4 Glance (Image)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_glance_up` | Glance API erisilebilir mi | bool (0/1) |
| `openstack_glance_images` | Toplam image sayisi | adet |
| `openstack_glance_image_bytes` | Image boyutu | byte |
| `openstack_glance_image_created_at` | Image olusturulma zamani | unix timestamp |

### 4.5 Keystone (Identity)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_identity_up` | Keystone API erisilebilir mi | bool (0/1) |
| `openstack_identity_domains` | Domain sayisi | adet |
| `openstack_identity_projects` | Proje sayisi | adet |
| `openstack_identity_users` | Kullanici sayisi | adet |
| `openstack_identity_groups` | Grup sayisi | adet |
| `openstack_identity_regions` | Region sayisi | adet |
| `openstack_identity_domain_info` | Domain bilgisi (meta) | info |
| `openstack_identity_project_info` | Proje bilgisi (meta) | info |

### 4.6 Placement

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_placement_up` | Placement API erisilebilir mi | bool (0/1) |
| `openstack_placement_resource_total` | Toplam kaynak | adet |
| `openstack_placement_resource_usage` | Kullanilan kaynak | adet |
| `openstack_placement_resource_reserved` | Rezerve kaynak | adet |
| `openstack_placement_resource_allocation_ratio` | Overcommit orani | ratio |

**Ek dimension'lar:**

| Dimension | Aciklama | Ornek |
|-----------|----------|-------|
| `hostname` | Compute host | `compute-01` |
| `resourcetype` | Kaynak tipi | `VCPU`, `MEMORY_MB`, `DISK_GB` |

### 4.7 Heat (Orchestration)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_heat_up` | Heat API erisilebilir mi | bool (0/1) |
| `openstack_heat_stack_status` | Stack durumu | enum |

### 4.8 Octavia (Load Balancer)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_loadbalancer_up` | Octavia API erisilebilir mi | bool (0/1) |
| `openstack_loadbalancer_total_loadbalancers` | Toplam LB sayisi | adet |
| `openstack_loadbalancer_total_pools` | Toplam pool sayisi | adet |
| `openstack_loadbalancer_total_amphorae` | Toplam amphora sayisi | adet |
| `openstack_loadbalancer_loadbalancer_status` | LB durumu | enum |
| `openstack_loadbalancer_pool_status` | Pool durumu | enum |
| `openstack_loadbalancer_amphora_status` | Amphora durumu | enum |

### 4.9 Trove (Database)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_trove_up` | Trove API erisilebilir mi | bool (0/1) |
| `openstack_trove_total_instances` | Toplam DB instance sayisi | adet |
| `openstack_trove_instance_status` | DB instance durumu | enum |
| `openstack_trove_instance_volume_size_gb` | DB volume boyutu | GB |
| `openstack_trove_instance_volume_used_gb` | DB kullanilan volume | GB |

### 4.10 Swift (Object Store)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_object_store_up` | Swift API erisilebilir mi | bool (0/1) |
| `openstack_object_store_objects` | Toplam nesne sayisi | adet |
| `openstack_object_store_bytes` | Toplam depolama boyutu | byte |

### 4.11 Manila (Shared File Systems)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_sharev2_up` | Manila API erisilebilir mi | bool (0/1) |
| `openstack_sharev2_shares_counter` | Toplam share sayisi | adet |
| `openstack_sharev2_share_gb` | Share boyutu | GB |
| `openstack_sharev2_share_status` | Share durumu | enum |

### 4.12 Magnum (Container Infra)

| Metrik | Aciklama | Birim |
|--------|----------|-------|
| `openstack_container_infra_up` | Magnum API erisilebilir mi | bool (0/1) |
| `openstack_container_infra_total_clusters` | Toplam cluster sayisi | adet |
| `openstack_container_infra_cluster_nodes` | Cluster node sayisi | adet |
| `openstack_container_infra_cluster_masters` | Cluster master sayisi | adet |
| `openstack_container_infra_cluster_status` | Cluster durumu | enum |

### 4.13 Quota Metrikleri

Tum OpenStack servisleri icin proje bazli kota metrikleri:

| Metrik | Aciklama |
|--------|----------|
| `openstack_nova_quota_cores` | vCPU kotasi |
| `openstack_nova_quota_ram` | RAM kotasi (MB) |
| `openstack_nova_quota_instances` | Instance kotasi |
| `openstack_neutron_quota_network` | Ag kotasi |
| `openstack_neutron_quota_port` | Port kotasi |
| `openstack_neutron_quota_router` | Router kotasi |
| `openstack_neutron_quota_floatingip` | Floating IP kotasi |
| `openstack_neutron_quota_security_group` | Security group kotasi |
| `openstack_neutron_quota_subnet` | Subnet kotasi |
| `openstack_cinder_volume_type_quota_gigabytes` | Volume tip bazli GB kotasi |

**Ek dimension'lar:**

| Dimension | Aciklama |
|-----------|----------|
| `tenant_id` | Proje UUID |

---

## Notlar

- **(counter)** ile isaretlenen metrikler surekli artan degerlerdir. Anlamli kullanim icin `rate()` veya `increase()` fonksiyonlari ile turetilmelidir.
- **(info)** metrikleri metadata tasiyan sabit degerli (genellikle 1) metriklerdir. Degerleri label'lardadir.
- **(enum)** metrikleri sayisal durumu temsil eder; anlamlari metrik aciklamasinda belirtilmistir.
- **(bool)** metrikleri 0 veya 1 deger alir.
