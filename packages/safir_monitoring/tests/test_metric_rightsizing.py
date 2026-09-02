import pytest


@pytest.mark.asyncio
class TestRightsizingClassification:
    async def test_classify_idle_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 2.0, "avg_memory": 5.0, "max_cpu": 3.0, "max_memory": 8.0,
              "daily_disk_io_mb": 100, "daily_net_io_mb": 50}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "idle"

    async def test_classify_not_idle_due_to_disk_io(self):
        """Disk I/O yuksekse idle degil"""
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 1.0, "avg_memory": 2.0, "max_cpu": 2.0, "max_memory": 3.0,
              "daily_disk_io_mb": 5000, "daily_net_io_mb": 50}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result != "idle"

    async def test_classify_not_idle_due_to_net_io(self):
        """Network I/O yuksekse idle degil"""
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 1.0, "avg_memory": 2.0, "max_cpu": 2.0, "max_memory": 3.0,
              "daily_disk_io_mb": 100, "daily_net_io_mb": 500}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result != "idle"

    async def test_classify_over_provisioned_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 15.0, "avg_memory": 20.0, "max_cpu": 25.0, "max_memory": 28.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "over_provisioned"

    async def test_classify_under_provisioned_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 85.0, "avg_memory": 70.0, "max_cpu": 95.0, "max_memory": 80.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "under_provisioned"

    async def test_classify_right_sized_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 50.0, "avg_memory": 50.0, "max_cpu": 60.0, "max_memory": 55.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "right_sized"

    async def test_classify_idle_takes_priority(self):
        """Idle siniflandirma diger kategorilerden once uygulanir"""
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 1.0, "avg_memory": 2.0, "max_cpu": 2.0, "max_memory": 3.0,
              "daily_disk_io_mb": 100, "daily_net_io_mb": 50}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "idle"

    async def test_classify_idle_no_io_data_defaults_zero(self):
        """Disk/net I/O verisi yoksa 0 kabul edilir (idle olabilir)"""
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 1.0, "avg_memory": 2.0, "max_cpu": 2.0, "max_memory": 3.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "idle"


@pytest.mark.asyncio
class TestRecommendation:
    async def test_over_provisioned_recommendation(self):
        from safir_monitoring.api.v1.metric_rightsizing import _compute_recommendation

        rec = _compute_recommendation(
            category="over_provisioned",
            max_cpu=20.0, max_memory=25.0,
            allocated_vcpu=8, allocated_memory_gb=16.0,
            over_threshold=30,
        )
        assert rec["vcpu"] < 8
        assert rec["memory_gb"] < 16.0

    async def test_under_provisioned_recommendation(self):
        from safir_monitoring.api.v1.metric_rightsizing import _compute_recommendation

        rec = _compute_recommendation(
            category="under_provisioned",
            max_cpu=90.0, max_memory=85.0,
            allocated_vcpu=4, allocated_memory_gb=8.0,
            over_threshold=30,
        )
        assert rec["vcpu"] > 4
        assert rec["memory_gb"] > 8.0
