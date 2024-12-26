import pytest
import json
import core_runner.handler as handler

from core_framework.models import (
    TaskPayload,
    DeploymentDetails as DeploymentDetailsClass,
)


@pytest.fixture
def task_payload():
    return TaskPayload(
        Task="deploy",
        DeploymentDetails=DeploymentDetailsClass(
            Client="my-client-test",
            Portfolio="my-portfolio",
            App="my-app",
            Branch="dev-branch",
            Build="build1",
        ),
    )


def test_runner(task_payload: TaskPayload):

    event = task_payload.model_dump()

    print(json.dumps(event, indent=2))

    response = handler.handler(event, {})

    print(json.dumps(response, indent=2))
