"""
Amazon Step Functions Lambda Resource to check Amazon SageMaker AutoPilot job status
"""

from boto3 import client

sm_client = client('sagemaker')


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    autopilot_job_name = event['AutopilotJobName']
    print(f'Autopilot JOb Name: {autopilot_job_name}')
    response = sm_client.describe_auto_ml_job(AutoMLJobName=autopilot_job_name)
    job_status = response['AutoMLJobStatus']
    job_sec_status = response['AutoMLJobSecondaryStatus']
    print(f'Autopilot Job {autopilot_job_name} is currently in {job_status}')
    result = {
        'AutopilotJobName': autopilot_job_name,
        'AutopilotJobStatus': job_status,
        'AutopilotSecondaryJobStatus': job_sec_status,
        'FailureReason': response.get('FailureReason', None),
        'MachineLearningTaskType': response.get('ProblemType', None)
    }
    if job_status == 'Completed':
        best_candidate = response['BestCandidate']
        inference_containers = best_candidate['InferenceContainers']
        multi_model_inference_containers = list(map(_set_multimodel_mode, inference_containers))
        result['InferenceContainers'] = multi_model_inference_containers
        result['BestCandidateName'] = best_candidate['CandidateName']
    return result


def _set_multimodel_mode(inference_container: dict) -> dict:
    """
    :param inference_container:
    :return:
    """
    inference_container['Mode'] = 'MultiModel'
    return inference_container
