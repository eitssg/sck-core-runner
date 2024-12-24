# Description: Executes the action runner step function
#
import core_logging as log
import time

import core_helper.aws as aws

import core_framework as util
from core_framework.models import TaskPayload

from core_execute.stepfn import local_step_function_client


def handler(event: dict, context: dict | None) -> dict:
    try:
        # event should have been created with TaskPayload.model_dump()
        task_payload = TaskPayload(**event)

        # Setup logging
        log.setup(task_payload.Identity)

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

        return {
            "Status": "ok",
            "Message": "Executed step function '{}'".format(execution_arn),
            "StepFunctionInput": task_payload.model_dump(),
            "ExecutionArn": execution_arn,
        }

    except Exception as e:
        log.error("Failed to execute step function", details={"Error": str(e)})
        return {
            "Status": "error",
            "Message": "Failed to execute step function",
            "Error": str(e),
        }


def lambda_start_execution(task_payload: TaskPayload, name: str) -> dict:

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

    region = util.get_region()
    arn = f"arn:aws:states:{region}:local:execution:stateMachineName:{name}"

    data = task_payload.model_dump()

    log.info(
        "Executing step function in local mode",
        details={"StepFunctionArn": arn, "Input": data},
    )

    sfn_client = local_step_function_client(region)
    return sfn_client.start_execution(stateMachineArn=arn, name=name, input=data)


def generate_execution_name(task_playload: TaskPayload) -> str:
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
