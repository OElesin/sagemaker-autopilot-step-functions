import sagemaker
from stepfunctions.steps import LambdaStep, Wait, Choice, Task, Chain, ChoiceRule, \
    Catch, Retry, Fail, EndpointConfigStep, EndpointStep
from boto3 import client
from stepfunctions.inputs import ExecutionInput
from stepfunctions.workflow import Workflow
from time import gmtime, strftime
from sagemaker.model_monitor import DataCaptureConfig
import utils

sagemaker_session = sagemaker.Session()
sagemaker_exec_role = utils.get_sagemaker_execution_role()
sfn_client = client('stepfunctions')
# define execution input
execution_input = ExecutionInput(schema={
    'AutoMLJobName': str,
    'ModelName': str,
    'S3InputData': str,
    'IamRole': str,
    'TargetColumnName': str,
    'S3OutputData': str,
    'Tags': dict,
    'EndpointName': str,
    'EndpointConfigName': str

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


model_step = Task(
    'CreateAutopilotModel',
    resource='arn:aws:states:::sagemaker:createModel',
    parameters={
        'Containers': check_autopilot_job_status.output()['Payload']['InferenceContainers'],
        'ModelName': execution_input['ModelName'],
        'ExecutionRoleArn': sagemaker_exec_role
    }
)

endpoint_config_step = EndpointConfigStep(
    'CreateModelEndpointConfig',
    endpoint_config_name=execution_input['EndpointConfigName'],
    model_name=execution_input['ModelName'],
    initial_instance_count=1,
    instance_type='ml.m4.xlarge',
    data_capture_config=DataCaptureConfig(
        enable_capture=True,
        sampling_percentage=100,
    )
)


endpoint_step = EndpointStep(
    'UpdateModelEndpoint',
    endpoint_name=execution_input['EndpointName'],
    endpoint_config_name=execution_input['EndpointConfigName'],
    update=False
)

# define Amazon CodeBuild Step Functions Task
deploy_rest_api_task = Task(
    'DeployRestAPI',
    resource='arn:aws:states:::codebuild:startBuild.sync',
    parameters={
        'ProjectName': utils.get_api_codebuild_project(),
        'EnvironmentVariablesOverride': [
            {
                'Name': 'SAGEMAKER_ENDPOINT',
                'Type': 'PLAIN_TEXT',
                'Value': execution_input['EndpointName']
            },
            {
                'Name': 'SAGEMAKER_AUTOPILOT_TARGET_MODEL',
                'Type': 'PLAIN_TEXT',
                'Value': '{}.tar.gz'.format(execution_input['ModelName'])
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
    state_machine_arn = autopilot_ml_workflow.create()
except sfn_client.exceptions.StateMachineAlreadyExists as e:
    print(e.message)
else:
    print("Updating workflow definition")
    state_machine_arn = autopilot_ml_workflow.update(workflow_definition)


utils.save_state_machine_arn(state_machine_arn)

timestamp_suffix = strftime('%d-%H-%M-%S', gmtime())

