import json
import core_runner.handler as handler
import os

os.environ["RUNNER_STEP_FUNCTION_ARN"] = (
    "arn:aws:states:ap-southeast-2:103294329576:stateMachine:CoreAutomationRunner-COLK3VLJIY0M"
)

event = {}

response = handler.handler(event, {})

print(response)
