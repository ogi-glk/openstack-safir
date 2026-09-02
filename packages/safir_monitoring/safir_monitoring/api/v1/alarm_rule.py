from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Header, Request, HTTPException, status, Query, Response
from oslo_log import log as logging

from safir_monitoring import schemas
from safir_monitoring.db import api as db_api
from safir_monitoring.common import policy, utils, thanos

LOG = logging.getLogger(__name__)
router = APIRouter()


async def _validate_notification_ids(notification_ids: List[str], project_id: str):
    for notif_id in notification_ids:
        try:
            notif = await db_api.get_notification(notif_id)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Notification {notif_id} not found"
            )
        if notif["project_id"] != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Notification {notif_id} does not belong to this project"
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
    "/{scope}/alarm-rules",
    description="List all alarm rules (admin: any project via query param, console: token project)",
    responses={
        200: {"model": List[schemas.AlarmRuleResponse]},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=List[schemas.AlarmRuleResponse],
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def list_alarm_rules(
    scope: str,
    request: Request,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    X_Auth_Token: str = Header(default=None)
) -> List[schemas.AlarmRuleResponse]:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        resolved_project_id = _resolve_project_id(scope, context)
        policy.authorize(context, 'alarm_rule:list', {"project_id": resolved_project_id})

        alarm_rules = await db_api.list_alarm_rules(resolved_project_id, enabled)
        return [schemas.AlarmRuleResponse(**rule) for rule in alarm_rules]
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in list_alarm_rules: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{scope}/alarm-rules/{alarm_rule_id}",
    description="Get a specific alarm rule",
    responses={
        200: {"model": schemas.AlarmRuleResponse},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        404: {"model": schemas.NotFoundMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=schemas.AlarmRuleResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def get_alarm_rule(
    scope: str,
    alarm_rule_id: str,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.AlarmRuleResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        rule = await db_api.get_alarm_rule(alarm_rule_id)
        policy.authorize(context, 'alarm_rule:get', {"project_id": rule["project_id"]})
        return schemas.AlarmRuleResponse(**rule)
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_alarm_rule: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{scope}/alarm-rules",
    description="Create a new alarm rule (console: project_id from token with inject, admin: project_id from body without inject)",
    responses={
        201: {"model": schemas.AlarmRuleCreateResponse},
        401: {"model": schemas.UnauthorizedMessage},
        403: {"model": schemas.ForbiddenMessage},
        500: {"model": schemas.InternalServerErrorMessage},
    },
    response_model=schemas.AlarmRuleCreateResponse,
    status_code=status.HTTP_201_CREATED,
    response_description="Created",
)
async def create_alarm_rule(
    scope: str,
    alarm_rule: schemas.AlarmRuleCreate,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.AlarmRuleCreateResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        project_id = _resolve_project_id(scope, context)
        inject = (scope == "console")
        policy.authorize(context, 'alarm_rule:create', {"project_id": project_id})

        if alarm_rule.notification_ids:
            await _validate_notification_ids(alarm_rule.notification_ids, project_id)

        if inject:
            expr = thanos.inject_project_id(alarm_rule.expr, project_id)
        else:
            expr = alarm_rule.expr

        await thanos.validate_promql_expression(expr)

        alarm_rule_id = await db_api.create_alarm_rule(
            project_id=project_id,
            rule_name=alarm_rule.rule_name,
            expr=expr,
            notification_ids=alarm_rule.notification_ids,
            inject_project_id=inject,
            rule_group=alarm_rule.rule_group,
            for_duration=alarm_rule.for_duration,
            severity=alarm_rule.severity,
            labels=alarm_rule.labels,
            annotations=alarm_rule.annotations,
            enabled=alarm_rule.enabled
        )
        LOG.info(f"Database entry created for alarm rule {alarm_rule_id}")

        try:
            rules = await db_api.list_alarm_rules(project_id, enabled=True)
            LOG.info(f"Rules fetched for project {project_id}: {len(rules)} rules")
            await thanos.update_project_rules_file(project_id, rules)
            LOG.info(f"Rules file updated for project {project_id}")
        except Exception as e:
            LOG.error(f"Failed to update Thanos rules file: {str(e)}", exc_info=True)

        return schemas.AlarmRuleCreateResponse(
            id=alarm_rule_id,
            message="Alarm rule created successfully",
            code=201,
            title="Created"
        )
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in create_alarm_rule: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{scope}/alarm-rules/{alarm_rule_id}",
    description="Update an alarm rule",
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
async def update_alarm_rule(
    scope: str,
    alarm_rule_id: str,
    alarm_rule: schemas.AlarmRuleUpdate,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.SuccessMessage:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        rule = await db_api.get_alarm_rule(alarm_rule_id)
        project_id = rule["project_id"]
        policy.authorize(context, 'alarm_rule:update', {"project_id": project_id})

        inject = (scope == "console")

        if alarm_rule.notification_ids is not None:
            await _validate_notification_ids(alarm_rule.notification_ids, project_id)

        expr = alarm_rule.expr
        if expr is not None:
            if inject:
                expr = thanos.inject_project_id(expr, project_id)
            await thanos.validate_promql_expression(expr)

        await db_api.update_alarm_rule(
            alarm_rule_id=alarm_rule_id,
            rule_name=alarm_rule.rule_name,
            rule_group=alarm_rule.rule_group,
            expr=expr,
            for_duration=alarm_rule.for_duration,
            severity=alarm_rule.severity,
            labels=alarm_rule.labels,
            annotations=alarm_rule.annotations,
            notification_ids=alarm_rule.notification_ids,
            inject_project_id=inject,
            enabled=alarm_rule.enabled
        )

        try:
            rules = await db_api.list_alarm_rules(project_id, enabled=True)
            await thanos.update_project_rules_file(project_id, rules)
        except Exception as e:
            LOG.error(f"Failed to update Thanos rules file: {str(e)}", exc_info=True)

        return schemas.SuccessMessage(
            message="Alarm rule updated successfully",
            code=200,
            title="OK"
        )
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in update_alarm_rule: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{scope}/alarm-rules/{alarm_rule_id}",
    description="Delete an alarm rule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_alarm_rule(
    scope: str,
    alarm_rule_id: str,
    request: Request,
    X_Auth_Token: str = Header(default=None)
):
    context = await utils.req_context_from_scope(request.scope)
    _validate_scope(scope, context)
    rule = await db_api.get_alarm_rule(alarm_rule_id)
    project_id = rule["project_id"]
    policy.authorize(context, 'alarm_rule:delete', {"project_id": project_id})

    await db_api.delete_alarm_rule(alarm_rule_id)

    try:
        rules = await db_api.list_alarm_rules(project_id, enabled=True)
        if rules:
            await thanos.update_project_rules_file(project_id, rules)
        else:
            await thanos.delete_project_rules_file(project_id)
    except Exception as e:
        LOG.error(f"Failed to update Thanos rules file: {str(e)}", exc_info=True)

    try:
        from safir_monitoring.api.v1 import alert_webhook as alerts_module
        await alerts_module.mark_rule_deleted_in_opensearch(project_id, alarm_rule_id)
    except Exception as e:
        LOG.error(f"Failed to mark OpenSearch docs as deleted: {str(e)}", exc_info=True)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{scope}/alarm-rules/{alarm_rule_id}/toggle",
    description="Enable or disable an alarm rule",
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
async def toggle_alarm_rule(
    scope: str,
    alarm_rule_id: str,
    toggle: schemas.AlarmRuleToggle,
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> schemas.SuccessMessage:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        rule = await db_api.get_alarm_rule(alarm_rule_id)
        project_id = rule["project_id"]
        policy.authorize(context, 'alarm_rule:toggle', {"project_id": project_id})

        await db_api.toggle_alarm_rule(alarm_rule_id, toggle.enabled)

        try:
            rules = await db_api.list_alarm_rules(project_id, enabled=True)
            await thanos.update_project_rules_file(project_id, rules)
        except Exception as e:
            LOG.error(f"Failed to update Thanos rules file: {str(e)}", exc_info=True)

        status_text = "enabled" if toggle.enabled else "disabled"
        return schemas.SuccessMessage(
            message=f"Alarm rule {status_text} successfully",
            code=200,
            title="OK"
        )
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in toggle_alarm_rule: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
