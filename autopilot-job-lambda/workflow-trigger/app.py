from boto3 import client
from time import gmtime, strftime
from os import getenv
from json import dumps


ssm_client = client('ssm')
sfn_client = client('stepfunctions')
sagemaker_exec_role = getenv('SAGEMAKER_EXECUTION_ROLE')
s3_input_data_path = getenv('S3_INPUT_DATA_PATH')
deployed_model_name = getenv('DEPLOYED_MODEL_NAME')
s3_output_path = getenv('S3_OUTPUT_PATH')
target_column_name = getenv('TARGET_COLUMN_NAME')

state_machine_arn = ssm_client.get_parameter(
    Name='AutopilotStateMachineWorkflowArn',
)['Parameter']['Value']


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    timestamp_suffix = strftime('%d-%H-%M-%S', gmtime())
    execution_input_dict = {
        'AutoMLJobName': f'autopilot-workflow-job-{timestamp_suffix}',
        'ModelName': deployed_model_name,
        'EndpointName': f'autopilot-workflow-endpoint',
        'S3InputData': s3_input_data_path,
        'TargetColumnName': target_column_name,
        'S3OutputData': s3_output_path,
        'IamRole': sagemaker_exec_role,
    }
    execution_input = dumps(execution_input_dict)
    sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        input=execution_input
    )
