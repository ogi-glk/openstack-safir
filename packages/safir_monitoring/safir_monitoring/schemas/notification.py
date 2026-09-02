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

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    name: str = Field(..., description="Notification name")
    type: Literal["email", "sms"] = Field(..., description="Notification type")
    value: str = Field(..., description="Email address or phone number")


class NotificationUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Notification name")
    type: Optional[Literal["email", "sms"]] = Field(None, description="Notification type")
    value: Optional[str] = Field(None, description="Email address or phone number")


class NotificationResponse(BaseModel):
    id: str = Field(..., description="Notification ID")
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Notification name")
    type: str = Field(..., description="Notification type")
    value: str = Field(..., description="Email address or phone number")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")


class NotificationCreateResponse(BaseModel):
    id: str = Field(..., description="Notification ID")
    message: str = Field(..., description="Message")
    code: int = Field(201, description="Code")
    title: str = Field("Created", description="Title")