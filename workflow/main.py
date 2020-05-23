import os
import sagemaker
from stepfunctions.steps import LambdaStep, Wait, Choice, Task, Chain, ChoiceRule, \
    Catch, Retry, Fail, ModelStep, EndpointConfigStep, EndpointStep
from stepfunctions.inputs import ExecutionInput
from stepfunctions.workflow import Workflow
from sagemaker.model import Model
from time import gmtime, strftime
import utils

workflow_execution_role = os.getenv('WORKFLOW_EXEC_ROLE')
sagemaker_session = sagemaker.Session()


# define execution input
execution_input = ExecutionInput(schema={
    'AutoMLJobName': str,
    'ModelName': str,
    'S3InputData': str,
    'IamRole': str,
    'TargetColumnName': str,
    'S3OutputData': str,
    'Tags': dict,
    'EndpointName': str
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

model_step = ModelStep(
    'SaveBestCandidateModel',
    model_name=execution_input['ModelName'],
    model=Model(
        model_data=check_autopilot_job_status.output()['Payload']['ModelData'],
        image=check_autopilot_job_status.output()['Payload']['Image']
    )
)

endpoint_config_step = EndpointConfigStep(
    'CreateModelEndpointConfig',
    endpoint_config_name=execution_input['ModelName'],
    model_name=execution_input['ModelName'],
    initial_instance_count=1,
    instance_type='ml.m4.xlarge'
)


endpoint_step = EndpointStep(
    'UpdateModelEndpoint',
    endpoint_name=execution_input['EndpointName'],
    endpoint_config_name=execution_input['ModelName'],
    update=False
)

# define Amazon CodeBuild Step Functions Task
deploy_rest_api_task = Task(
    'DeployRestAPI',
    resource='arn:aws:states:::codebuild:startBuild.sync',
    parameters={
        'ProjectName': 'HelloBuild',
        'EnvironmentVariablesOverride': [
            {
                'Name': 'SageMakerEndpointName',
                'Type': 'PLAIN_TEXT',
                'Value': execution_input['EndpointName']
            }
        ]
    }
)

# happy path
model_and_endpoint_step = Chain([
    model_step,
    endpoint_config_step,
    endpoint_step,
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
    next_step=model_and_endpoint_step
)

workflow_definition = Chain([
    create_autopilot_job_step,
    check_autopilot_job_status,
    check_job_wait_state,
    check_job_choice
])

autopilot_ml_workflow = Workflow(
    name="AutopilotStateMachineWorkflow",
    definition=workflow_definition,
    role=utils.get_workflow_role()
)


try:
    workflow_arn = autopilot_ml_workflow.create()
except BaseException as e:
    print(e)
    # workflow_arn = autopilot_ml_workflow.update(workflow_definition)


timestamp_suffix = strftime('%d-%H-%M-%S', gmtime())
# autopilot_ml_workflow.execute(
#     inputs={
#         'AutoMLJobName': f'autopilot-workflow-job-{timestamp_suffix}',
#         'ModelName': f'autopilot-workflow-{timestamp_suffix}-model',
#         'S3InputData': '',
#         'TargetColumnName': '',
#         'S3OutputData': '',
#         'IamRole': '',
#         'EndpointName': f'autopilot-workflow-{timestamp_suffix}-endpoint'
#     }
# )
