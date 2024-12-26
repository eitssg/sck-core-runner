"""Executes the action runner step function"""

import core_logging as log
import time

import core_helper.aws as aws

import core_framework as util
from core_framework.models import TaskPayload

import core_execute.stepfn as local


def handler(event: dict, context: dict | None) -> dict:
    """
    Executes the action runner step function.

    This lambda function expects a TaskPayload object as input and executes the action runner step function.

    The TaskPayload is validated and a unique execution name is generated based on the TaskPayload details.

    The return value is the following dictionary:

    .. code-block:: json

        {
           "Status": "ok | error",
          "Message": "Executed step function '<execution_arn>' | Failed to execute step function",
          "StepFunctionInput": { "task": "... the task payload ..." },
          "ExecutionArn": "<execution_arn>"
        }


    Args:
        event (dict): The task payload object
        context (dict | None): The context of the execution

    Returns:
        dict: The result of the execution
    """
    try:
        # event should have been created with TaskPayload.model_dump()
        task_payload = TaskPayload(**event)

        # Setup logging
        log.setup(task_payload.Identity)

        log.info("Executing step function", details=task_payload.model_dump())

        name = generate_execution_name(task_payload)

        if util.is_local_mode():
            sfn_response = local_start_execution(task_payload, name)
        else:
            sfn_response = lambda_start_execution(task_payload, name)

        execution_arn = sfn_response["executionArn"]

        log.info(
            "Execute Engine started successfully",
            details={"ExecutionArn": execution_arn},
        )

        result = {
            "Status": "ok",
            "Message": "Executed step function '{}'".format(execution_arn),
            "StepFunctionInput": task_payload.model_dump(),
            "ExecutionArn": execution_arn,
        }

        log.debug("Result", details=result)

        return result

    except Exception as e:
        log.error("Failed to execute step function", details={"Error": str(e)})
        return {
            "Status": "error",
            "Message": "Failed to execute step function",
            "Error": str(e),
        }


def lambda_start_execution(task_payload: TaskPayload, name: str) -> dict:
    """
    Start the execution of a step function in AWS. This will start the step function
    in the AWS Step Functions service.

    Args:
        task_payload (TaskPayload): The task payload to execute
        name (str): The name of the execution

    Returns:
        dict: Result of the job start request
    """
    region = util.get_region()
    arn = util.get_step_function_arn()
    data = task_payload.model_dump_json()

    log.info(
        "Executing step function in AWS",
        details={"StepFunctionArn": arn, "Input": data},
    )

    sfn_client = aws.step_functions_client(region)
    return sfn_client.start_execution(stateMachineArn=arn, name=name, input=data)


def local_start_execution(task_payload: TaskPayload, name: str) -> dict:
    """
    Start the execution of a step function in local mode. This means it will
    run in a shell process in the background and continue to run until it fails,
    completes, or is stopped by the OS.

    Args:
        task_payload (TaskPayload): The task payload to execute
        name (str): the executin name

    Returns:
        dict: Result of the job start request
    """
    region = util.get_region()
    arn = f"arn:aws:states:{region}:local:execution:stateMachineName:{name}"

    data = task_payload.model_dump()

    log.info(
        "Executing step function in local mode",
        details={"StepFunctionArn": arn, "Input": data},
    )

    sfn_client = local.step_function_client(region)
    return sfn_client.start_execution(stateMachineArn=arn, name=name, input=data)


def generate_execution_name(task_playload: TaskPayload) -> str:
    """
    Generate a unique name for the execution.

    This will create a name based on deployment details and the current time.

    It will concatenate the following fields:

    - Task
    - Portfolio
    - App
    - BranchShortName
    - Build
    - Current time in seconds

    The ressult will be, for example:  ``deploy-portfolio-app-branch-build-1234567890``

    Args:
        task_playload (TaskPayload): The task paload to generate the name for

    Returns:
        str: The name of the execution
    """
    dd = task_playload.DeploymentDetails
    return "-".join(
        [
            task_playload.Task,
            dd.Portfolio,
            dd.App or "",
            dd.BranchShortName or "",
            dd.Build or "",
            str(int(time.time())),
        ]
    )
