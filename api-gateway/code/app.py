from boto3 import client
from os import getenv
from json import loads


SAGEMAKER_ENDPOINT = getenv('SAGEMAKER_ENDPOINT')
SAGEMAKER_AUTOPILOT_TARGET_MODEL = getenv('SAGEMAKER_AUTOPILOT_TARGET_MODEL')
sm_runtime = client('sagemaker-runtime')


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    request_body = loads(event['body'])
    response = sm_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType='text/csv',
        Accept='text/csv',
        Body=request_body,
        TargetModel=SAGEMAKER_AUTOPILOT_TARGET_MODEL
    )
    return response['Body'].read().decode("utf-8")
