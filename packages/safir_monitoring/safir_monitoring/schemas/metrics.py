# safir_monitoring/schemas/metrics.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ============================================================================
# METRIC SCHEMAS
# ============================================================================

class MetricDataPoint(BaseModel):
    """Tek bir metrik veri noktası"""
    timestamp: int = Field(..., description="Unix timestamp (seconds)")
    value: str = Field(..., description="Metric value")


class MetricTimeSeries(BaseModel):
    """Tek bir time series (labels + data points)"""
    metric: Dict[str, str] = Field(..., description="Metric labels")
    values: List[List] = Field(..., description="Time series data [[timestamp, value], ...]")


class MetricData(BaseModel):
    """Metric query response data"""
    metric: str = Field(..., description="Metric name or PromQL query")
    start_time: int = Field(..., description="Start time (unix timestamp)")
    end_time: int = Field(..., description="End time (unix timestamp)")
    step: str = Field(..., description="Query resolution step")
    results: List[MetricTimeSeries] = Field(..., description="Time series results")


class MetricSuccessResponse(BaseModel):
    """Metric API success response"""
    data: MetricData = Field(..., description="Metric data")
    message: str = Field(..., description="Success message")
    code: int = Field(200, description="HTTP status code")
    title: str = Field("OK", description="Response title")


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class BadRequestMessage(BaseModel):
    """400 Bad Request response"""
    detail: str = Field(..., description="Error detail")


class UnauthorizedMessage(BaseModel):
    """401 Unauthorized response"""
    detail: str = Field(..., description="Error detail")


class ForbiddenMessage(BaseModel):
    """403 Forbidden response"""
    detail: str = Field(..., description="Error detail")


class InternalServerErrorMessage(BaseModel):
    """500 Internal Server Error response"""
    detail: str = Field(..., description="Error detail")


# ============================================================================
# MEASUREMENTS SCHEMAS
# ============================================================================

class MeasurementSeries(BaseModel):
    """Tek bir olcum serisi"""
    name: str = Field(..., description="Metric name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Metric dimensions/labels")
    measurements: List[List] = Field(..., description="[[timestamp, value], ...]")


class MeasurementsResponse(BaseModel):
    """Measurements endpoint response"""
    data: List[MeasurementSeries] = Field(..., description="Measurement series list")
    message: str = Field("Measurements fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================

class StatisticsSeries(BaseModel):
    """Tek bir istatistik serisi"""
    name: str = Field(..., description="Metric name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Metric dimensions/labels")
    columns: List[str] = Field(..., description="Column names (e.g., ['timestamp', 'avg', 'min', 'max', 'count', 'sum'])")
    statistics: List[List] = Field(..., description="Statistics data rows")


class StatisticsResponse(BaseModel):
    """Statistics endpoint response"""
    data: List[StatisticsSeries] = Field(..., description="Statistics series list")
    message: str = Field("Statistics fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# METRIC NAMES SCHEMA
# ============================================================================

class MetricNamesResponse(BaseModel):
    """Metric names endpoint response"""
    metric_names: List[str] = Field(..., description="Available metric names")
    type: Optional[str] = Field(None, description="Metric type filter (user/system)")
    message: str = Field("Metric names fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# DIMENSION SCHEMAS
# ============================================================================

class DimensionNamesResponse(BaseModel):
    """Dimension names endpoint response"""
    dimension_names: List[str] = Field(..., description="Label/dimension key names")
    message: str = Field("Dimension names fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class DimensionValuesResponse(BaseModel):
    """Dimension values endpoint response"""
    dimension_name: str = Field(..., description="Label/dimension key")
    dimension_values: List[str] = Field(..., description="Values for the dimension")
    message: str = Field("Dimension values fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# HOST / VM SCHEMAS
# ============================================================================

class HostElement(BaseModel):
    """Tek bir host bilgisi"""
    name: str = Field(..., description="Host name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Host labels")


class HostListResponse(BaseModel):
    """Host list endpoint response"""
    elements: List[HostElement] = Field(..., description="Host list")
    message: str = Field("Hosts fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class VMElement(BaseModel):
    """Tek bir VM bilgisi"""
    name: str = Field(..., description="VM name")
    instance_id: str = Field(..., description="OpenStack instance ID")
    project_id: str = Field(default="", description="Owner project ID")
    hostname: str = Field(default="", description="Compute host name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="VM labels")


class VMListResponse(BaseModel):
    """VM list endpoint response"""
    elements: List[VMElement] = Field(..., description="VM list")
    message: str = Field("VMs fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# TOP-N SCHEMAS
# ============================================================================

class TopNHostElement(BaseModel):
    """Top-N host sonucu"""
    hostname: str = Field(..., description="Host name")
    value: float = Field(..., description="Metric value")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Additional labels")


class TopNHostResponse(BaseModel):
    """Top-N host endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used for ranking (avg/max/min)")
    elements: List[TopNHostElement] = Field(..., description="Top N hosts")
    message: str = Field("Top N hosts fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class TopNVMElement(BaseModel):
    """Top-N VM sonucu"""
    vm_name: str = Field(..., description="VM name")
    instance_id: str = Field(..., description="OpenStack instance ID")
    project_id: str = Field(default="", description="Owner project ID")
    hostname: str = Field(default="", description="Compute host (admin only)")
    value: float = Field(..., description="Metric value")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Additional labels")


class TopNVMResponse(BaseModel):
    """Top-N VM endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used for ranking (avg/max/min)")
    elements: List[TopNVMElement] = Field(..., description="Top N VMs")
    message: str = Field("Top N VMs fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# WOW CHANGE SCHEMAS
# ============================================================================

class WoWChangeElement(BaseModel):
    """Tek bir seri icin Week-over-Week degisim"""
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Series dimensions")
    current_week_value: float = Field(..., description="Current week statistic value")
    previous_week_value: float = Field(..., description="Previous week statistic value")
    change: float = Field(..., description="Absolute change")
    change_percent: Optional[float] = Field(None, description="Percentage change (null if previous is 0)")


class WoWChangeResponse(BaseModel):
    """WoW change endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used (avg/max/min)")
    elements: List[WoWChangeElement] = Field(..., description="Per-series WoW changes")
    message: str = Field("Week-over-week change calculated successfully")
    code: int = Field(200)
    title: str = Field("OK")