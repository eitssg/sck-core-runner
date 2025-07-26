"""Executes the action runner step function"""

import core_logging as log
import time

import core_helper.aws as aws

import core_framework as util
from core_framework.models import TaskPayload
from core_framework.constants import TR_RESPONSE


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
        log.setup(task_payload.identity)
        log.info("Executing step function", details=task_payload.model_dump())

        name = generate_execution_name(task_payload)
        sfn_response = start_execution(task_payload, name)
        execution_arn = sfn_response["executionArn"]

        log.info(
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
    region = util.get_region()
    arn = util.get_step_function_arn()
    data = task_payload.model_dump()

    log.info(
        "Executing step function in AWS",
        details={"StepFunctionArn": arn, "Input": data},
    )

    sfn_client = aws.step_functions_client(region=region)
    return sfn_client.start_execution(stateMachineArn=arn, name=name, input=data)


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
