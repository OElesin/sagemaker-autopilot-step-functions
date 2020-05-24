from boto3 import client
from os import getenv
from json import loads


SAGEMAKER_ENDPOINT = getenv('SAGEMAKER_ENDPOINT')
sm_runtime = client('sagemaker-runtime')


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    request_body = loads(event['body'])
    print("Hello world")
    return request_body
