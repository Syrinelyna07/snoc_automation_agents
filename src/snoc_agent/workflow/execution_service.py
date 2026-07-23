"""Durable, idempotent business-operation execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from snoc_agent.business_api import BusinessAPI, BusinessAPIError, BusinessAPITransportError
from snoc_agent.db.models import Execution, Operation
from snoc_agent.db.repositories import ExecutionRepository
from snoc_agent.db.session import SessionFactory, session_scope
from snoc_agent.domain.enums import ExecutionStatus, OperationAction, OperationStatus
from snoc_agent.domain.errors import UnsafeExecutionError
from snoc_agent.domain.state_machine import assert_operation_transition
from snoc_agent.domain.value_objects import canonical_action


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    execution_id: uuid.UUID
    status: ExecutionStatus
    detail: str


class ExecutionService:
    def __init__(
        self,
        session_factory: SessionFactory,
        business_api: BusinessAPI,
        *,
        vpn_allowed_additional_fields: frozenset[str] = frozenset(),
    ) -> None:
        self.session_factory = session_factory
        self.business_api = business_api
        self.vpn_allowed_additional_fields = vpn_allowed_additional_fields

    @staticmethod
    def idempotency_key(operation: Operation) -> str:
        return f"{operation.id}:{operation.current_revision}"

    def execute(self, operation_id: uuid.UUID) -> ExecutionOutcome:
        with session_scope(self.session_factory) as session:
            operation = session.get(Operation, operation_id)
            if operation is None:
                raise LookupError(f"operation {operation_id} was not found")
            key = self.idempotency_key(operation)
            prior = ExecutionRepository(session).by_idempotency_key(key)
            if prior is not None:
                return ExecutionOutcome(
                    prior.id,
                    ExecutionStatus(prior.status),
                    "identical operation revision was already recorded",
                )
            if OperationStatus(operation.status) != OperationStatus.READY_FOR_VALIDATION:
                raise UnsafeExecutionError(
                    f"operation {operation.id} is {operation.status}, not READY_FOR_VALIDATION"
                )
            action = canonical_action(operation.action)
            pdv_code = operation.pdv_code
            phone = operation.phone
            additional = dict(operation.additional_payload)
            preflight_error: str | None = None
            if pdv_code is None:
                preflight_error = "PDV is absent after validation"
            elif action in {OperationAction.VPN_ACCESS, OperationAction.OTP_NUMBER_CHANGE} and (
                phone is None
            ):
                preflight_error = "phone is absent after validation"
            elif action == OperationAction.UNKNOWN:
                preflight_error = "operation action is unsupported"
            else:
                allowed = (
                    self.vpn_allowed_additional_fields
                    if action == OperationAction.VPN_ACCESS
                    else frozenset()
                )
                unexpected = set(additional) - allowed
                if unexpected:
                    preflight_error = (
                        "operation contains unapproved additional fields: "
                        + ", ".join(sorted(unexpected))
                    )
            if preflight_error:
                execution = Execution(
                    operation_id=operation.id,
                    operation_revision=operation.current_revision,
                    idempotency_key=key,
                    endpoint=f"rejected_preflight:{operation.action}",
                    request_payload={
                        "pdv_code": pdv_code,
                        "phone": phone,
                        **additional,
                    },
                    response_body={"error": preflight_error},
                    dry_run=True,
                    attempt_count=0,
                    status=ExecutionStatus.FAILED.value,
                )
                ExecutionRepository(session).add(execution)
                operation.status = OperationStatus.ESCALATED.value
                operation.execution_eligible = False
                return ExecutionOutcome(execution.id, ExecutionStatus.FAILED, preflight_error)
            assert_operation_transition(
                OperationStatus(operation.status), OperationStatus.EXECUTING
            )
            operation.status = OperationStatus.EXECUTING.value
            payload = {
                "pdv_code": operation.pdv_code,
                "phone": operation.phone,
                **operation.additional_payload,
            }
            execution = Execution(
                operation_id=operation.id,
                operation_revision=operation.current_revision,
                idempotency_key=key,
                endpoint=f"pending:{operation.action}",
                request_payload=payload,
                dry_run=True,
                attempt_count=0,
                status=ExecutionStatus.PENDING.value,
            )
            ExecutionRepository(session).add(execution)
            execution_id = execution.id

        if pdv_code is None:
            raise AssertionError("execution preflight allowed a missing PDV")
        try:
            if action == OperationAction.VPN_ACCESS:
                if phone is None:
                    raise AssertionError("execution preflight allowed a missing VPN phone")
                result = self.business_api.create_vpn_access(
                    pdv_code=pdv_code,
                    phone=phone,
                    idempotency_key=key,
                    additional_payload=additional,
                )
            elif action == OperationAction.OTP_NUMBER_CHANGE:
                if phone is None:
                    raise AssertionError("execution preflight allowed a missing OTP phone")
                result = self.business_api.update_otp(
                    pdv_code=pdv_code, new_phone=phone, idempotency_key=key
                )
            elif action == OperationAction.ACCOUNT_UNBLOCK:
                result = self.business_api.unlock_account(pdv_code=pdv_code, idempotency_key=key)
            elif action == OperationAction.PASSWORD_RESET:
                result = self.business_api.reset_password(pdv_code=pdv_code, idempotency_key=key)
            else:
                raise UnsafeExecutionError(f"unsupported action {action}")
        except Exception as exc:
            status = (
                ExecutionStatus.UNKNOWN
                if isinstance(exc, BusinessAPITransportError)
                or not isinstance(exc, BusinessAPIError)
                else ExecutionStatus.FAILED
            )
            with session_scope(self.session_factory) as session:
                stored_execution = session.get(Execution, execution_id)
                operation = session.get(Operation, operation_id)
                if stored_execution:
                    stored_execution.status = status.value
                    stored_execution.attempt_count = max(1, getattr(exc, "attempts", 1))
                    stored_execution.response_body = {
                        "error": str(exc)[:2000],
                        "exception_type": type(exc).__name__,
                    }
                if operation:
                    operation.status = OperationStatus.ESCALATED.value
                    operation.execution_eligible = False
            return ExecutionOutcome(execution_id, status, str(exc))

        with session_scope(self.session_factory) as session:
            stored_execution = session.get(Execution, execution_id)
            operation = session.get(Operation, operation_id)
            if stored_execution is None or operation is None:
                raise RuntimeError(
                    "execution or operation disappeared while API call was in flight"
                )
            stored_execution.endpoint = result.endpoint
            stored_execution.response_status = result.status_code
            stored_execution.response_body = result.response_body
            stored_execution.dry_run = result.dry_run
            stored_execution.attempt_count = result.attempts
            stored_execution.status = (
                ExecutionStatus.SUCCEEDED.value if result.success else ExecutionStatus.FAILED.value
            )
            if result.success:
                assert_operation_transition(
                    OperationStatus(operation.status), OperationStatus.COMPLETED
                )
                operation.status = OperationStatus.COMPLETED.value
                operation.execution_eligible = False
            else:
                operation.status = OperationStatus.ESCALATED.value
                operation.execution_eligible = False
            return ExecutionOutcome(
                stored_execution.id,
                ExecutionStatus(stored_execution.status),
                "business API accepted operation"
                if result.success
                else "business API rejected operation",
            )
