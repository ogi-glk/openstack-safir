from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ============================================================================
# PREDICTION SCHEMAS
# ============================================================================

class PredictionWorstCase(BaseModel):
    capacity_full_date: Any = Field(..., description="Worst case capacity full date (ISO or message)")
    days_remaining: Any = Field(..., description="Worst case days remaining (int or message)")


class PredictionConfidence(BaseModel):
    upper: float = Field(..., description="Upper confidence bound")
    lower: float = Field(..., description="Lower confidence bound")


class PredictionResponse(BaseModel):
    status: str = Field(..., description="Status: stable, warning, healthy")
    capacity_full_date: Any = Field(..., description="Capacity full date (ISO or message)")
    days_remaining: Any = Field(..., description="Days remaining (int or message)")
    current_usage: float = Field(..., description="Current usage value")
    total_capacity: float = Field(..., description="Total capacity")
    usage_percentage: float = Field(..., description="Usage percentage")
    daily_growth: float = Field(..., description="Daily growth rate")
    resource_type: str = Field(..., description="Resource type (cpu/memory/disk)")
    prediction_method: str = Field(..., description="Method used: prophet or none")
    worst_case: PredictionWorstCase = Field(..., description="Worst case scenario")
    confidence: PredictionConfidence = Field(..., description="Confidence interval")
    dimension: Optional[str] = Field(None, description="Host or VM identifier")
    scope: Optional[str] = Field(None, description="system (for system-wide predictions)")
    metric_source: Optional[str] = Field(None, description="Data source: real or placement")
    message: Optional[str] = Field(None, description="Status message")


class SystemReportResource(BaseModel):
    status: str = Field(...)
    current_usage: float = Field(...)
    total_capacity: float = Field(...)
    usage_percentage: float = Field(...)
    daily_growth: float = Field(...)
    capacity_full_date: Any = Field(...)
    days_remaining: Any = Field(...)


class SystemReportResponse(BaseModel):
    report: Dict[str, SystemReportResource] = Field(..., description="CPU, memory, disk predictions")
    period_days: int = Field(..., description="Forecast period in days")


# ============================================================================
# TREND GRAPH SCHEMAS
# ============================================================================

class TrendDataPoint(BaseModel):
    date: str = Field(...)
    actual_value: float = Field(...)
    trend_value: float = Field(...)
    yhat: float = Field(...)
    yhat_upper: float = Field(...)
    yhat_lower: float = Field(...)


class TrendFuturePrediction(BaseModel):
    date: str = Field(...)
    predicted_value: float = Field(...)
    trend_value: float = Field(...)
    upper_bound: float = Field(...)
    lower_bound: float = Field(...)


class TrendStatistics(BaseModel):
    current_usage: float = Field(...)
    total_capacity: float = Field(...)
    usage_percentage: float = Field(...)
    daily_growth: float = Field(...)
    prediction_method: str = Field(...)
    capacity_full_date: Any = Field(...)
    days_remaining: Any = Field(...)


class TrendCapacityLine(BaseModel):
    value: float = Field(...)
    label: str = Field(...)


class TrendGraphResponse(BaseModel):
    resource_type: str = Field(...)
    unit: Optional[str] = Field(None)
    dimension: Optional[str] = Field(None)
    scope: Optional[str] = Field(None)
    data_points: List[TrendDataPoint] = Field(...)
    future_predictions: List[TrendFuturePrediction] = Field(...)
    statistics: TrendStatistics = Field(...)
    capacity_line: TrendCapacityLine = Field(...)


# ============================================================================
# MAX VALUE SCHEMA
# ============================================================================

class MaxValueResponse(BaseModel):
    resource_type: str = Field(...)
    dimension: str = Field(...)
    current_max: float = Field(...)
    predicted_max: float = Field(...)
    period_days: int = Field(...)


# ============================================================================
# RIGHTSIZING SCHEMAS
# ============================================================================

class RightsizingVMElement(BaseModel):
    instance_id: str = Field(...)
    name: str = Field(...)
    project_id: str = Field(default="")
    hostname: str = Field(default="")
    avg_cpu: Optional[float] = Field(None, description="Average CPU usage (%)")
    avg_memory: Optional[float] = Field(None, description="Average memory usage (%)")
    max_cpu: Optional[float] = Field(None, description="Max CPU usage (%)")
    max_memory: Optional[float] = Field(None, description="Max memory usage (%)")
    avg_disk_io_bytes_sec: Optional[float] = Field(None, description="Average disk I/O (bytes/sec)")
    avg_net_io_bytes_sec: Optional[float] = Field(None, description="Average network I/O (bytes/sec)")
    daily_disk_io_mb: Optional[float] = Field(None, description="Daily total disk I/O (MB)")
    daily_net_io_mb: Optional[float] = Field(None, description="Daily total network I/O (MB)")
    allocated_vcpu: Optional[int] = Field(None)
    allocated_memory_gb: Optional[float] = Field(None)
    recommendation: Optional[Dict[str, Any]] = Field(None)


class RightsizingListResponse(BaseModel):
    vms: List[RightsizingVMElement] = Field(...)
    total_count: int = Field(...)
    period_days: int = Field(...)
    message: str = Field(...)
    code: int = Field(200)
    title: str = Field("OK")


class RightsizingSummary(BaseModel):
    total_vms: int = Field(...)
    idle: int = Field(...)
    over_provisioned: int = Field(...)
    under_provisioned: int = Field(...)
    right_sized: int = Field(...)


class PotentialSavings(BaseModel):
    vcpu: int = Field(...)
    memory_gb: float = Field(...)


class RightsizingReportResponse(BaseModel):
    summary: RightsizingSummary = Field(...)
    idle_vms: List[RightsizingVMElement] = Field(...)
    over_provisioned_vms: List[RightsizingVMElement] = Field(...)
    under_provisioned_vms: List[RightsizingVMElement] = Field(...)
    potential_savings: PotentialSavings = Field(...)
    period_days: int = Field(...)
    message: str = Field("Rightsizing report generated successfully")
    code: int = Field(200)
    title: str = Field("OK")
