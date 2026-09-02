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

import re
from typing import List
from fastapi import APIRouter, Header, Request, HTTPException, status, Response
from oslo_log import log as logging

from safir_monitoring import schemas
from safir_monitoring.db import api as db_api
from safir_monitoring.common import policy, utils

LOG = logging.getLogger(__name__)
router = APIRouter()

VALID_TYPES = {"email", "webhook"}


def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_url(url: str) -> bool:
    pattern = r'^https?://.+'
    return re.match(pattern, url) is not None


def validate_notification_value(type: str, value: str):
    if type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type '{type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}"
        )
    if type == "email" and not is_valid_email(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    if type == "webhook" and not is_valid_url(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook URL format. Must start with http:// or https://"
        )


def _validate_scope(scope: str, context):
    if scope not in ("console", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope must be 'console' or 'admin'"
        )
    if scope == "admin" and "admin" not in (context.roles or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin scope requires admin role"
        )


def _resolve_project_id(scope: str, context) -> str:
    if scope == "admin":
        return "system"
    if not context.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id not found in token for console scope"
        )
    return context.project_id


@router.get(
    "/{scope}/notifications",
    description="List all notifications (admin: any project via query param, console: token project)",
    responses={
        200: {"model": List[schemas.NotificationResponse]},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=List[schemas.NotificationResponse],
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def list_notifications(
    scope: str,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> List[schemas.NotificationResponse]:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        resolved_project_id = _resolve_project_id(scope, context)
        policy.authorize(context, 'notification:list', {"project_id": resolved_project_id})

        notifications = await db_api.list_notifications(resolved_project_id)
        return [schemas.NotificationResponse(**dict(n)) for n in notifications]
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in list_notifications: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{scope}/notifications/{notification_id}",
    description="Get a specific notification",
    responses={
        200: {"model": schemas.NotificationResponse},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        404: {"model": schemas.NotFoundMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=schemas.NotificationResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def get_notification(
    scope: str,
    notification_id: str,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.NotificationResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        notif = await db_api.get_notification(notification_id)
        policy.authorize(context, 'notification:get', {"project_id": notif["project_id"]})
        return schemas.NotificationResponse(**dict(notif))
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_notification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{scope}/notifications",
    description="Create a new notification (console: project_id from token, admin: project_id from body)",
    responses={
        201: {"model": schemas.NotificationCreateResponse},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=schemas.NotificationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    response_description="Created",
)
async def create_notification(
    scope: str,
    notification: schemas.NotificationCreate,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.NotificationCreateResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        project_id = _resolve_project_id(scope, context)
        policy.authorize(context, 'notification:create', {"project_id": project_id})

        validate_notification_value(notification.type, notification.value)

        notification_id = await db_api.create_notification(
            project_id,
            notification.name,
            notification.type,
            notification.value
        )

        return schemas.NotificationCreateResponse(
            id=notification_id,
            message="Notification created successfully",
            code=201,
            title="Created"
        )
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in create_notification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{scope}/notifications/{notification_id}",
    description="Update a notification",
    responses={
        200: {"model": schemas.SuccessMessage},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        404: {"model": schemas.NotFoundMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=schemas.SuccessMessage,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def update_notification(
    scope: str,
    notification_id: str,
    notification: schemas.NotificationUpdate,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.SuccessMessage:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        notif = await db_api.get_notification(notification_id)
        policy.authorize(context, 'notification:update', {"project_id": notif["project_id"]})

        new_type = notification.type if notification.type is not None else notif["type"]
        new_value = notification.value if notification.value is not None else notif["value"]
        validate_notification_value(new_type, new_value)

        await db_api.update_notification(
            notification_id,
            notification.name,
            notification.type,
            notification.value
        )

        return schemas.SuccessMessage(
            message="Notification updated successfully",
            code=200,
            title="OK"
        )
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in update_notification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{scope}/notifications/{notification_id}",
    description="Delete a notification",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    scope: str,
    notification_id: str,
    request: Request,
    X_Auth_Token: str = Header(default=None)
):
    context = await utils.req_context_from_scope(request.scope)
    _validate_scope(scope, context)
    notif = await db_api.get_notification(notification_id)
    project_id = notif["project_id"]

    policy.authorize(context, 'notification:delete', {"project_id": project_id})

    if await db_api.is_notification_in_use(notification_id, project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete notification: used by active alarm rules"
        )

    await db_api.delete_notification(notification_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
