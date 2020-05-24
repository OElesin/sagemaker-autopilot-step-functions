import boto3
from sagemaker.model import Model
from sagemaker.pipeline import PipelineModel


ssm_client = boto3.client('ssm')


def get_workflow_role() -> str:
    """
    :return:
    """
    response = ssm_client.get_parameter(
        Name='AutopilotWorkflowExecRole',
    )
    return response['Parameter']['Value']


def get_api_codebuild_project() -> str:
    """
    :return:
    """
    response = ssm_client.get_parameter(
        Name='RestApiBuildProject',
    )
    return response['Parameter']['Value']


def get_sagemaker_execution_role():
    """
    Convert SageMaker Autopilot Inference Containers to PipelineModel
    :return:
    """
    response = ssm_client.get_parameter(
        Name='SageMakerExecutionRole',
    )
    return response['Parameter']['Value']


def save_state_machine_arn(state_machine_arn: str):
    """
    Save state machine ARN to Amazon SSM Parameter Store
    :param state_machine_arn:
    :return:
    """
    response = ssm_client.put_parameter(
        Name='AutopilotStateMachineWorkflowArn',
        Description='SageMaker Autopilot Step Function State machine ARN',
        Value=state_machine_arn,
        Type='String',
        Overwrite=True
    )
    print(response)
    return None
