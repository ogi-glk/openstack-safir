from pydantic import BaseModel, Field
from typing import List


# ============================================================================
# QUOTA SCHEMAS
# ============================================================================

class QuotaProgressValue(BaseModel):
    """Quota progress bar değeri"""
    label: str = Field(..., description="Progress label (e.g., '10/20 Cores')")
    percent: float = Field(..., ge=0, le=100, description="Percentage (0-100)")


# Project Quota Schemas
class QuotaResponse(BaseModel):
    """Project quota response"""
    instances: QuotaProgressValue = Field(..., description="Instance quota")
    vcpus: QuotaProgressValue = Field(..., description="VCPU quota")
    memory: QuotaProgressValue = Field(..., description="Memory quota")
    disk: QuotaProgressValue = Field(..., description="Disk quota")


class QuotaSuccessResponse(BaseModel):
    """Quota API success response"""
    data: QuotaResponse = Field(..., description="Quota data")
    message: str = Field(..., description="Success message")
    code: int = Field(200, description="HTTP status code")
    title: str = Field("OK", description="Response title")


# Host Quota Schemas
class HostQuotaTotal(BaseModel):
    """Host quota toplam değerleri"""
    vcpus: QuotaProgressValue = Field(..., description="Total VCPU quota")
    memory: QuotaProgressValue = Field(..., description="Total Memory quota")


class HostQuotaItem(BaseModel):
    """Tek bir host için quota bilgisi"""
    hostname: str = Field(..., description="Host name")
    vcpus: QuotaProgressValue = Field(..., description="Host VCPU quota")
    memory: QuotaProgressValue = Field(..., description="Host Memory quota")


class HostQuotaResponse(BaseModel):
    """Host quota response data"""
    total: HostQuotaTotal = Field(..., description="Total quota across all hosts")
    hosts: List[HostQuotaItem] = Field(..., description="Per-host quota breakdown")


class HostQuotaSuccessResponse(BaseModel):
    """Host quota API success response"""
    data: HostQuotaResponse = Field(..., description="Host quota data")
    message: str = Field(..., description="Success message")
    code: int = Field(200, description="HTTP status code")
    title: str = Field("OK", description="Response title")


# ============================================================================
# ERROR SCHEMAS (Eğer mevcut schemas.py'da yoksa ekle)
# ============================================================================

class UnauthorizedMessage(BaseModel):
    """401 Unauthorized response"""
    detail: str = Field(..., description="Error detail")


class ForbiddenMessage(BaseModel):
    """403 Forbidden response"""
    detail: str = Field(..., description="Error detail")


class NotFoundMessage(BaseModel):
    """404 Not Found response"""
    detail: str = Field(..., description="Error detail")


class InternalServerErrorMessage(BaseModel):
    """500 Internal Server Error response"""
    detail: str = Field(..., description="Error detail")