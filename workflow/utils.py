import boto3

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
