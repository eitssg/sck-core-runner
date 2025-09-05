"""Executes the action runner step function"""

import core_logging as log
import uuid
import copy
from datetime import datetime, timezone
import time
import threading
import json
from pydoc import locate
import os

import core_helper.aws as aws

import core_framework as util
from core_framework.models import TaskPayload
from core_framework.constants import TR_RESPONSE
from jsonpath_ng.ext import parse as jp_parse


def handler(event: dict, context: dict | None) -> dict:
    """
    Executes the action runner step function.

    This Lambda function is the entry point for starting the core_execute Step Function workflow.
    It expects a TaskPayload object (as a dictionary) and triggers the Step Function execution.

    :param event: The task payload object, typically created via TaskPayload.model_dump().
    :type event: dict
    :param context: Lambda context object (optional).
    :type context: dict or None

    :returns: Dictionary containing the execution result. Example::

        {
            "Response": {
                "Status": "ok | error",
                "Message": "Executed step function '<execution_arn>' | Failed to execute step function",
                "StepFunctionInput": { ...task payload... },
                "ExecutionArn": "<execution_arn>"
            }
        }

    :raises Exception: Any error during execution is logged and returned in the response.
    """
    try:
        task_payload = TaskPayload(**event)
        log.set_correlation_id(task_payload.correlation_id)

        log.setup(task_payload.identity)
        log.debug("Executing step function runner", details=task_payload.model_dump())

        name = generate_execution_name(task_payload)
        sfn_response = start_execution(task_payload, name)
        execution_arn = sfn_response["executionArn"]

        log.debug(
            "Execute Engine started successfully",
            details={"ExecutionArn": execution_arn},
        )

        result = {
            "Status": "ok",
            "Message": f"Executed step function '{execution_arn}'",
            "StepFunctionInput": task_payload.model_dump(),
            "ExecutionArn": execution_arn,
        }

        log.debug("Result", details=result)
        return {TR_RESPONSE: result}

    except Exception as e:
        log.error("Failed to execute step function", details={"Error": str(e)})
        return {
            "Status": "error",
            "Message": "Failed to execute step function",
            "Error": str(e),
        }


def start_execution(task_payload: TaskPayload, name: str) -> dict:
    """
    Start the execution of a Step Function in AWS.

    This function initializes the Step Functions client and starts a new execution
    using the provided task payload and execution name.

    :param task_payload: The task payload to execute.
    :type task_payload: TaskPayload
    :param name: The unique name for the execution.
    :type name: str

    :returns: Dictionary containing the Step Functions start_execution response.
    :rtype: dict

    :raises Exception: If the AWS Step Functions client fails to start the execution.
    """

    # we also use this name in the fake ARN as well as for the real client.
    region = util.get_automation_region()

    if util.is_local_mode():
        # Create a fake, local state-machine arn
        arn = f"arn:aws:states:{region}:local:execution:{name}-{uuid.uuid4().hex[:8]}"
        return start_execution_local(arn, name, task_payload)
    else:

        arn = util.get_step_function_arn()
        data = task_payload.model_dump()

        sfn_client = aws.step_functions_client(region=region)
        return sfn_client.start_execution(
            stateMachineArn=arn,
            name=name,
            input=data,
            traceHeader=task_payload.correlation_id,
        )


def start_execution_local(arn: str, name: str, task_payload: TaskPayload) -> dict:
    """
    Start execution in background thread and return immediately.

    This is NOT for lambda.  We use this ONLY in local mode to emulate
    the step-function background operations nature.

    This mimics real Step Functions behavior where start_execution returns
    immediately and the execution runs asynchronously.
    """

    def background_execution():
        """Run the execution in background with workflow loop."""
        try:
            log.set_correlation_id(task_payload.correlation_id)
            current_data = task_payload.model_dump()
            execution_arn = arn
            iteration = 0

            # Minimal Lambda-like context for local execution
            class LocalLambdaContext:
                def __init__(self, timeout_ms: int | None = None, function_name: str = "core_execute.handler"):
                    self._start = time.monotonic()

                    # Default 15 minutes; override via env LOCAL_LAMBDA_TIMEOUT_MS
                    self._timeout_ms = int(timeout_ms or int(os.getenv("LOCAL_LAMBDA_TIMEOUT_MS", "900000")))
                    self.aws_request_id = log.get_correlation_id()
                    self.function_name = function_name
                    self.invoked_function_arn = execution_arn
                    self.memory_limit_in_mb = 256
                    self.log_group_name = log.get_identity()
                    self.log_stream_name = datetime.now(timezone.utc).strftime("%Y/%m/%d/[local]%H%M%S")

                def get_remaining_time_in_millis(self) -> int:
                    elapsed_ms = int((time.monotonic() - self._start) * 1000)
                    return max(0, self._timeout_ms - elapsed_ms)

            # ------- JSONPath helpers using jsonpath-ng -------
            def jp_get(data: dict, path: str):
                if not isinstance(path, str):
                    return None
                if path == "$":
                    return data
                expr = jp_parse(path)
                matches = expr.find(data)
                return matches[0].value if matches else None

            def jp_set(data: dict, path: str, value):
                if path == "$":
                    return value
                expr = jp_parse(path)
                matches = expr.find(data)
                if matches:
                    for m in matches:
                        m.full_path.update(data, value)
                    return data
                if not path.startswith("$."):
                    raise RuntimeError(f"Unsupported ResultPath: {path}")
                parts = path[2:].split(".")
                out = copy.deepcopy(data)
                cur = out
                for p in parts[:-1]:
                    nxt = cur.get(p)
                    if not isinstance(nxt, dict):
                        nxt = {}
                        cur[p] = nxt
                    cur = nxt
                cur[parts[-1]] = value
                return out

            def apply_input_path(data: dict, definition: dict):
                ip = definition.get("InputPath")
                return jp_get(data, ip) if isinstance(ip, str) else data

            def apply_output_path(data: dict, definition: dict):
                op = definition.get("OutputPath")
                return jp_get(data, op) if isinstance(op, str) else data

            def build_parameters(params_def, data: dict):
                if params_def is None:
                    return data
                if isinstance(params_def, dict) and params_def.get("$") == "$" and len(params_def) == 1:
                    return data

                def transform(node):
                    if isinstance(node, dict):
                        out = {}
                        for k, v in node.items():
                            if k.endswith(".$") and isinstance(v, str):
                                out[k[:-2]] = jp_get(data, v)
                            else:
                                out[k] = transform(v)
                        return out
                    if isinstance(node, list):
                        return [transform(x) for x in node]
                    return node

                return transform(params_def)

            def build_selector(selector_def, task_result: dict):
                if selector_def is None:
                    return task_result

                def transform(node):
                    if isinstance(node, dict):
                        out = {}
                        for k, v in node.items():
                            if k.endswith(".$") and isinstance(v, str):
                                out[k[:-2]] = jp_get(task_result, v)
                            else:
                                out[k] = transform(v)
                        return out
                    if isinstance(node, list):
                        return [transform(x) for x in node]
                    return node

                return transform(selector_def)

            def apply_result_path(input_obj: dict, result_obj, definition: dict):
                if "ResultPath" in definition:
                    rp = definition.get("ResultPath")
                    if rp is None:
                        return input_obj
                    if rp == "$":
                        if isinstance(input_obj, dict) and isinstance(result_obj, dict):
                            merged = copy.deepcopy(input_obj)
                            merged.update(result_obj)
                            return merged
                        return result_obj
                    return jp_set(input_obj, rp, result_obj)
                return result_obj

            # ------- Resource resolver using stdlib (pydoc.locate) -------
            def resolve_resource(resource):
                # Allow direct callables in local dicts
                if callable(resource):
                    return resource
                if isinstance(resource, str):
                    # pydoc.locate supports both "pkg.mod.attr" and "pkg.mod:attr"
                    obj = locate(resource) or locate(resource.replace(":", "."))
                    if callable(obj):
                        return obj
                    raise RuntimeError(f"Resource not found or not callable: {resource}")
                raise RuntimeError(f"Unsupported Resource format: {resource!r}. Use 'module.submodule:function' or a callable.")

            # Allow JSON string or dict for the machine definition
            machine = step_function_definition
            if isinstance(machine, str):
                machine = json.loads(machine)

            states = machine.get("States", {})
            state = machine.get("StartAt")
            if state not in states:
                raise RuntimeError(f"Invalid StartAt state: {state}")

            # ------- State handlers (each returns tuple (next_state, terminated: bool)) -------

            def handle_task(state_name: str, definition: dict):
                nonlocal current_data, iteration
                iteration += 1
                task_input = apply_input_path(current_data, definition)
                payload = build_parameters(definition.get("Parameters"), task_input)

                # Resolve Resource
                resource = definition.get("Resource")
                callable_res = resolve_resource(resource)

                # Retry (single block)
                retry_cfg = (definition.get("Retry") or [])[:1]
                attempt = 0
                interval = float(retry_cfg[0].get("IntervalSeconds", 1)) if retry_cfg else 1.0
                backoff = float(retry_cfg[0].get("BackoffRate", 1.0)) if retry_cfg else 1.0
                max_attempts = int(retry_cfg[0].get("MaxAttempts", 1)) if retry_cfg else 1
                retry_errors = set(retry_cfg[0].get("ErrorEquals", [])) if retry_cfg else set()

                redirected = False
                while True:
                    try:
                        # Simulate a fresh Lambda invocation context per attempt
                        ctx = LocalLambdaContext()
                        raw_result = callable_res(payload, ctx)
                        if not isinstance(raw_result, dict):
                            raise RuntimeError(f"Task returned non-dict in '{state_name}': {type(raw_result)}")

                        selected = build_selector(definition.get("ResultSelector"), raw_result)
                        out_obj = apply_result_path(task_input, selected, definition)
                        current_data = apply_output_path(out_obj, definition)
                        break

                    except Exception as e:
                        attempt += 1
                        err_code = "States.TaskFailed"
                        retryable = ("States.ALL" in retry_errors) or (err_code in retry_errors)
                        if retryable and attempt < max_attempts:
                            log.warning(
                                "Task failed, retrying",
                                details={
                                    "state": state_name,
                                    "attempt": attempt,
                                    "error": str(e),
                                },
                            )
                            time.sleep(interval)
                            interval *= backoff
                            continue

                        # Catch
                        catches = definition.get("Catch") or []
                        for c in catches:
                            err_set = set(c.get("ErrorEquals") or [])
                            if "States.ALL" in err_set or err_code in err_set:
                                error_payload = {"Error": err_code, "Cause": str(e)}
                                rp = c.get("ResultPath", "$")
                                current_data = apply_output_path(
                                    apply_result_path(task_input, error_payload, {"ResultPath": rp}),
                                    c,
                                )
                                next_after_catch = c.get("Next")
                                return next_after_catch, False
                        # No catch
                        log.error(
                            "Task failed with no catch",
                            details={
                                "state": state_name,
                                "error": str(e),
                                "attempts": attempt,
                            },
                        )
                        return "ExecutionFailed", False

                if definition.get("End") is True:
                    log.debug(
                        "Background execution reached End",
                        details={"iterations": iteration, "final_result": current_data},
                    )
                    return None, True
                next_state = definition.get("Next")
                if not next_state:
                    raise RuntimeError(f"Missing 'Next' or 'End' in Task state '{state_name}'")
                return next_state, False

            def handle_choice(state_name: str, definition: dict):
                nonlocal current_data
                choice_input = apply_input_path(current_data, definition)
                choices = definition.get("Choices") or []
                next_state = None
                for choice in choices:
                    var_path = choice.get("Variable")
                    left = jp_get(choice_input, var_path) if var_path else None
                    if "StringEquals" in choice and left == choice["StringEquals"]:
                        next_state = choice.get("Next")
                        break
                if not next_state:
                    next_state = definition.get("Default")
                if not next_state:
                    raise RuntimeError(f"No matching Choice and no Default in '{state_name}'")
                current_data = apply_output_path(choice_input, definition)
                if definition.get("End") is True:
                    return None, True
                return next_state, False

            def handle_wait(state_name: str, definition: dict):
                nonlocal current_data
                wait_input = apply_input_path(current_data, definition)
                seconds = definition.get("Seconds")
                if seconds is None and "SecondsPath" in definition:
                    seconds = int(jp_get(wait_input, definition["SecondsPath"]) or 0)
                if seconds is None and "Timestamp" in definition:
                    try:
                        target = definition["Timestamp"]
                        if isinstance(target, str):
                            if target.endswith("Z"):
                                target_dt = datetime.fromisoformat(target.replace("Z", "+00:00"))
                            else:
                                target_dt = datetime.fromisoformat(target)
                            seconds = max(
                                0,
                                int((target_dt - datetime.now(timezone.utc)).total_seconds()),
                            )
                    except Exception:
                        seconds = 0
                if seconds is None and "TimestampPath" in definition:
                    try:
                        target_val = jp_get(wait_input, definition["TimestampPath"])
                        if isinstance(target_val, str):
                            if target_val.endswith("Z"):
                                target_dt = datetime.fromisoformat(target_val.replace("Z", "+00:00"))
                            else:
                                target_dt = datetime.fromisoformat(target_val)
                            seconds = max(
                                0,
                                int((target_dt - datetime.now(timezone.utc)).total_seconds()),
                            )
                    except Exception:
                        seconds = 0
                time.sleep(int(seconds or 1))
                current_data = apply_output_path(wait_input, definition)
                if definition.get("End") is True:
                    return None, True
                return definition.get("Next"), False

            def handle_pass(state_name: str, definition: dict):
                nonlocal current_data
                pass_input = apply_input_path(current_data, definition)
                if "Result" in definition:
                    pass_result = definition["Result"]
                else:
                    pass_result = (
                        build_parameters(definition.get("Parameters"), pass_input) if "Parameters" in definition else pass_input
                    )
                out_obj = apply_result_path(pass_input, pass_result, definition)
                current_data = apply_output_path(out_obj, definition)
                if definition.get("End") is True:
                    return None, True
                return definition.get("Next"), False

            def handle_succeed(state_name: str, definition: dict):
                log.debug(
                    f"Background execution completed: {execution_arn}",
                    details={"iterations": iteration, "final_result": current_data},
                )
                return None, True

            def handle_fail(state_name: str, definition: dict):
                log.error(
                    f"Execution failed: {execution_arn}",
                    details={"iteration": iteration, "result": current_data},
                )
                return None, True

            handlers = {
                "Task": handle_task,
                "Choice": handle_choice,
                "Wait": handle_wait,
                "Pass": handle_pass,
                "Succeed": handle_succeed,
                "Fail": handle_fail,
            }

            while True:
                definition = states.get(state)
                stype = definition.get("Type")
                log.debug(
                    "State transition",
                    details={"state": state, "type": stype, "iteration": iteration},
                )

                handler_fn = handlers.get(stype)
                if not handler_fn:
                    raise RuntimeError(f"Unknown state type '{stype}' in state '{state}'")

                next_state, terminated = handler_fn(state, definition)
                if terminated:
                    break
                state = next_state

        except Exception as e:
            log.error(
                f"Background execution failed: {execution_arn}",
                details={"error": str(e), "iteration": iteration},
            )

    # Start background thread
    thread = threading.Thread(target=background_execution, name=name)
    thread.daemon = True
    thread.start()

    # Return immediately (like real Step Functions)
    return {"executionArn": arn, "startDate": datetime.now(timezone.utc)}


def generate_execution_name(task_payload: TaskPayload) -> str:
    """
    Generate a unique name for the Step Function execution.

    The execution name is constructed from key deployment details and the current time,
    ensuring uniqueness and traceability. The format is::

        <task>-<portfolio>-<app>-<branch_short_name>-<build>-<timestamp>

    Example::

        deploy-myportfolio-myapp-main-1234-1721920000

    :param task_payload: The task payload to generate the name for.
    :type task_payload: TaskPayload

    :returns: Unique execution name string.
    :rtype: str
    """
    dd = task_payload.deployment_details
    return "-".join(
        [
            task_payload.task,
            dd.portfolio,
            dd.app or "",
            dd.branch_short_name or "",
            dd.build or "",
            str(int(time.time())),
        ]
    )


step_function_definition = {
    "Comment": "Core Automation Execution State Machine",
    "StartAt": "ExecuteActions",
    "States": {
        "ExecuteActions": {
            "Type": "Task",
            "Resource": "core_execute.handler:handler",
            "Parameters": {"$": "$"},
            "Retry": [
                {
                    "ErrorEquals": [
                        "States.TaskFailed",
                        "Lambda.ServiceException",
                        "Lambda.AWSLambdaException",
                    ],
                    "IntervalSeconds": 5,
                    "MaxAttempts": 3,
                    "BackoffRate": 2.0,
                }
            ],
            "Catch": [
                {
                    "ErrorEquals": ["States.ALL"],
                    "Next": "ExecutionFailed",
                    "ResultPath": "$.error",
                }
            ],
            "Next": "CheckExecutionStatus",
        },
        "CheckExecutionStatus": {
            "Type": "Choice",
            "Choices": [
                {
                    "Variable": "$.FlowControl",
                    "StringEquals": "success",
                    "Next": "ExecutionComplete",
                },
                {
                    "Variable": "$.FlowControl",
                    "StringEquals": "failure",
                    "Next": "ExecutionFailed",
                },
                {
                    "Variable": "$.FlowControl",
                    "StringEquals": "execute",
                    "Next": "WaitAndContinue",
                },
            ],
            "Default": "ExecutionFailed",
        },
        "WaitAndContinue": {"Type": "Wait", "Seconds": 10, "Next": "ExecuteActions"},
        "ExecutionComplete": {
            "Type": "Succeed",
            "Comment": "All actions completed successfully",
        },
        "ExecutionFailed": {
            "Type": "Fail",
            "Comment": "Action execution failed",
            "Cause": "One or more actions failed during execution",
        },
    },
}
