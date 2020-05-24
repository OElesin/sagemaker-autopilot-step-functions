import sagemaker
from stepfunctions.steps import LambdaStep, Wait, Choice, Task, Chain, ChoiceRule, \
    Catch, Retry, Fail, EndpointConfigStep, EndpointStep
from stepfunctions.inputs import ExecutionInput
from stepfunctions.workflow import Workflow
from time import gmtime, strftime
import utils

sagemaker_session = sagemaker.Session()
sagemaker_exec_role = utils.get_sagemaker_execution_role()

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
        'ProjectName': utils.get_api_codebuild_project(),
        'EnvironmentVariablesOverride': [
            {
                'Name': 'SAGEMAKER_ENDPOINT',
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

state_machine_arn = autopilot_ml_workflow.state_machine_arn

if state_machine_arn is None:
    state_machine_arn = autopilot_ml_workflow.create()
else:
    state_machine_arn = autopilot_ml_workflow.update(workflow_definition)


utils.save_state_machine_arn(state_machine_arn)

timestamp_suffix = strftime('%d-%H-%M-%S', gmtime())

# Uncomment below when you're ready to execute workflow
# autopilot_ml_workflow.execute(
#     inputs={
#         'AutoMLJobName': f'autopilot-workflow-job-{timestamp_suffix}',
#         'ModelName': f'autopilot-workflow-{timestamp_suffix}-model',
#         'EndpointName': f'autopilot-workflow-{timestamp_suffix}-endpoint',
#         'S3InputData': '',
#         'TargetColumnName': '',
#         'S3OutputData': '',
#         'IamRole': sagemaker_exec_role,
#     }
# )

# TODO:
