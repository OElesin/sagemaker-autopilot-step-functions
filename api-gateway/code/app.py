from boto3 import client
from os import getenv
from json import loads, dumps


SAGEMAKER_ENDPOINT = getenv('SAGEMAKER_ENDPOINT')
SAGEMAKER_AUTOPILOT_TARGET_MODEL = getenv('SAGEMAKER_AUTOPILOT_TARGET_MODEL')
sm_runtime = client('sagemaker-runtime')


def respond(data, status=501):
    return {
        "headers": {
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST,PUT",
            "Access-Control-Allow-Origin": "*"
        },
        "statusCode": status,
        "body": dumps(data)
    }


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    request_method = event['httpMethod']
    request_body = loads(event['body'])

    if request_method == 'OPTIONS':
        return respond("This is an empty OPTIONS Request", 200)

    response = sm_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType='text/csv',
        Accept='text/csv',
        Body=request_body,
        TargetModel=SAGEMAKER_AUTOPILOT_TARGET_MODEL
    )
    payload = {
        'Prediction': response['Body'].read().decode("utf-8"),
        'SageMakerEndpointName': SAGEMAKER_ENDPOINT
    }
    return respond(payload, 200)
