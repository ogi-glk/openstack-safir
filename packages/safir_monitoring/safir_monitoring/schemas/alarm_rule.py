# Copyright 2021 99cloud
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class AlarmRuleCreate(BaseModel):
    rule_name: str = Field(..., description="Rule name")
    expr: str = Field(..., description="PromQL expression")
    notification_ids: List[str] = Field(..., description="Notification IDs")
    rule_group: str = Field("default", description="Rule group")
    for_duration: Optional[str] = Field(None, description="For duration")
    severity: Optional[str] = Field(None, description="Severity level")
    labels: Optional[dict] = Field(None, description="Labels")
    annotations: Optional[dict] = Field(None, description="Annotations")
    enabled: bool = Field(True, description="Enabled status")


class AlarmRuleUpdate(BaseModel):
    rule_name: Optional[str] = Field(None, description="Rule name")
    rule_group: Optional[str] = Field(None, description="Rule group")
    expr: Optional[str] = Field(None, description="PromQL expression")
    for_duration: Optional[str] = Field(None, description="For duration")
    severity: Optional[str] = Field(None, description="Severity level")
    labels: Optional[dict] = Field(None, description="Labels")
    annotations: Optional[dict] = Field(None, description="Annotations")
    notification_ids: Optional[List[str]] = Field(None, description="Notification IDs")
    enabled: Optional[bool] = Field(None, description="Enabled status")


class AlarmRuleResponse(BaseModel):
    id: str = Field(..., description="Alarm rule ID")
    project_id: str = Field(..., description="Project ID")
    rule_name: str = Field(..., description="Rule name")
    rule_group: str = Field(..., description="Rule group")
    expr: str = Field(..., description="PromQL expression")
    for_duration: Optional[str] = Field(None, description="For duration")
    severity: Optional[str] = Field(None, description="Severity level")
    labels: Optional[dict] = Field(None, description="Labels")
    annotations: Optional[dict] = Field(None, description="Annotations")
    notification_ids: List[str] = Field(..., description="Notification IDs")
    inject_project_id: bool = Field(..., description="project_id inject edilip edilmediği")
    enabled: bool = Field(..., description="Enabled status")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")


class AlarmRuleCreateResponse(BaseModel):
    id: str = Field(..., description="Alarm rule ID")
    message: str = Field(..., description="Message")
    code: int = Field(201, description="Code")
    title: str = Field("Created", description="Title")


class AlarmRuleToggle(BaseModel):
    enabled: bool = Field(..., description="Enabled status")