"""
Amazon Step Functions Lambda Resource to create Amazon SageMaker AutoPilot job
"""
from boto3 import client
from time import gmtime, strftime, sleep

sm_client = client('sagemaker')


def lambda_handler(event, context):
    """
    :param event:
    :param context:
    :return:
    """
    print(event)
    timestamp_suffix = strftime('%d-%H-%M-%S', gmtime())
    autopilot_job_name = f'aws-samples-autopilot-workflow-{timestamp_suffix}'
    configuration: dict = event['Configuration']
    input_data = configuration.get('S3InputData')
    job_execution_role = configuration.get('IamRole')
    target_column = configuration.get('TargetColumnName')
    output_path = configuration.get('S3OutputData')
    tags = configuration.get('Tags')
    autopilot_job_tags = generate_job_tags(tags)
    autopilot_job_config: dict = {
        'CompletionCriteria': {
            'MaxRuntimePerTrainingJobInSeconds': 600,
            'MaxCandidates': 5,
            'MaxAutoMLJobRuntimeInSeconds': 5400
        }
    }

    autopilot_input_data_config = [
        {
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': input_data
                }
            },
            'TargetAttributeName': target_column
        }
    ]

    autopilot_output_data_config = {
        'S3OutputPath': output_path
    }

    response = sm_client.create_auto_ml_job(
        AutoMLJobName=autopilot_job_name,
        InputDataConfig=autopilot_input_data_config,
        OutputDataConfig=autopilot_output_data_config,
        AutoMLJobConfig=autopilot_job_config,
        RoleArn=job_execution_role,
        Tags=autopilot_job_tags
    )
    return {
        'AutopilotJobName': autopilot_job_name,
        'AutopilotJobArn': response['AutoMLJobArn']
    }


def generate_job_tags(raw_tags):
    """
    :param raw_tags:
    :return:
    """
    base_tags = [
        {
            'Key': 'provider',
            'Value': 'elesin.olalekan@gmail.com'
        },
    ]
    if raw_tags is None:
        return base_tags
    input_tags = [{'Key': key, 'Value': value} for key, value in raw_tags]
    return base_tags + input_tags
