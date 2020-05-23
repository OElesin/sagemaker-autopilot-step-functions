import os
import sagemaker
import stepfunctions
from stepfunctions.steps import LambdaStep, Wait, Choice, Task, Chain, ChoiceRule, Catch, Retry, Fail
from stepfunctions.inputs import ExecutionInput
from stepfunctions.workflow import Workflow


workflow_execution_role = os.getenv('WORKFLOW_EXEC_ROLE')
sagemaker_session = sagemaker.Session()


# define execution input
execution_input = ExecutionInput(schema={
    'AutoMLJobName': str,
    'S3InputData': str,
    'IamRole': str,
    'TargetColumnName': str,
    'S3OutputData': str,
    'Tags': dict
})

# TODO: make this a notification
workflow_failure = Fail(
    'WorkflowFailed'
)

# create autopilot lambda step
create_autopilot_job_step = LambdaStep(
    'StartAutopilotJob',
    parameters={
        'FunctionName': 'CreateAutopilotJob',
        'Payload': {
            'Configuration': {
                'AutoMLJobName': execution_input['AutoMLJobName'],
                'S3InputData': execution_input['S3InputData'],
                'IamRole': execution_input['IamRole'],
                'TargetColumnName': execution_input['TargetColumnName'],
                'S3OutputData': execution_input['S3OutputData'],
                'Tags': execution_input['Tags']
            }
        }
    }
)

create_autopilot_job_step.add_retry(Retry(
    error_equals=["States.TaskFailed"],
    interval_seconds=15,
    max_attempts=2,
    backoff_rate=4.0
))

create_autopilot_job_step.add_catch(Catch(
    error_equals=["States.TaskFailed"],
    next_step=workflow_failure
))

check_autopilot_job_status = LambdaStep(
    'CheckAutopilotJobStatus',
    parameters={
        'FunctionName': 'CheckAutopilotJobStatus',
        'Payload': {
            'AutopilotJobName': create_autopilot_job_step.output()['Payload']['AutopilotJobName']
        }
    }
)

check_job_wait_state = Wait(
    state_id="Wait",
    seconds=360
)

check_job_choice = Choice(
    state_id="IsAutopilotJobComplete"
)

# define Amazon CodeBuild Step Functions Task
deploy_rest_api_task = Task(
    'DeployRestAPI',
    resource='arn:aws:states:::codebuild:startBuild.sync',
    parameters={
        'environmentVariablesOverride': [
            {
                'name': 'SageMakerEndpointName',
                'type': 'PLAIN_TEXT',
                'value': 'some_endpoint'
            }
        ]
    }
)

# happy path
happy_path = Chain([
    create_autopilot_job_step,
    deploy_rest_api_task
])


# define choice
check_job_choice.add_choice(
    ChoiceRule.StringEquals(
        variable=check_autopilot_job_status.output()['Payload']['AutopilotJobStatus'],
        value='InProgress'
    ),
    next_step=check_autopilot_job_status
)

check_job_choice.add_choice(
    ChoiceRule.StringEquals(
        variable=check_autopilot_job_status.output()['Payload']['AutopilotJobStatus'],
        value='Stopping'
    ),
    next_step=check_autopilot_job_status
)

check_job_choice.add_choice(
    ChoiceRule.StringEquals(
        variable=check_autopilot_job_status.output()['Payload']['AutopilotJobStatus'],
        value='Failed'
    ),
    next_step=workflow_failure
)

check_job_choice.add_choice(
    ChoiceRule.StringEquals(
        variable=check_autopilot_job_status.output()['Payload']['AutopilotJobStatus'],
        value='Stopped'
    ),
    next_step=workflow_failure
)

check_job_choice.add_choice(
    ChoiceRule.StringEquals(
        variable=check_autopilot_job_status.output()['Payload']['AutopilotJobStatus'],
        value='Completed'
    ),
    next_step=happy_path
)
