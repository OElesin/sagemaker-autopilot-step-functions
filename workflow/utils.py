import boto3

ssm_client = boto3.client('ssm')


def get_workflow_role() -> str:
    """
    :param key:
    :return:
    """
    response = ssm_client.get_parameter(
        Name='AutopilotWorkflowExecRole',
    )
    return response['Parameter']['Value']
