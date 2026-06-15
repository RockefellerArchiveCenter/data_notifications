#!/usr/bin/env python3

import json
import logging
import traceback
from os import getenv

import boto3
import urllib3

http = urllib3.PoolManager()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


full_config_path = f"/{getenv('ENV')}/{getenv('APP_CONFIG_PATH')}"


def parse_attributes(attributes):
    """Parses attributes from messages."""
    service = attributes['service']['stringValue']
    outcome = attributes['outcome']['stringValue'].lower()
    message = attributes.get('message', {}).get('stringValue')
    object_type = attributes['object_type']['stringValue']
    object_status = attributes['object_status']['stringValue']
    object_id = attributes.get('object_id', {}).get('stringValue')
    return service, outcome, message, object_type, object_status, object_id


def structure_teams_message(title, message, facts):
    """Structures Teams message using arguments."""
    body = [
        {
            "type": "TextBlock",
                    "size": "default",
                    "weight": "bolder",
                    "text": title,
                    "style": "heading",
                    "wrap": True,
                    "color": "attention"
        },
        {
            "type": "TextBlock",
                    "text": message,
                    "wrap": True
        },

    ]

    body.append(
        {
            "type": "FactSet",
            "facts": [{"title": k, "value": v} for k, v in facts.items()]
        }
    )
    notification = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body
                }
            }
        ]
    }

    return json.dumps(notification)


def send_teams_message(message, url):
    """Delivers message to Teams channel endpoint."""
    response = http.request(
        'POST',
        url,
        headers={
            'Content-Type': 'application/json'},
        body=message)
    logger.info('Status Code: {}'.format(response.status))
    logger.info('Response: {}'.format(response.data))


def get_config(ssm_parameter_path):
    """Fetch config values from Parameter Store.

    Args:
        ssm_parameter_path (str): Path to parameters

    Returns:
        configuration (dict): all parameters found at the supplied path.
    """
    configuration = {}
    try:
        ssm_client = boto3.client(
            'ssm', region_name=getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        param_details = ssm_client.get_parameters_by_path(
            Path=ssm_parameter_path,
            Recursive=False,
            WithDecryption=True)

        for param in param_details.get('Parameters', []):
            param_path_array = param.get('Name').split("/")
            section_position = len(param_path_array) - 1
            section_name = param_path_array[section_position]
            configuration[section_name] = param.get('Value')

    except BaseException:
        print("Encountered an error loading config from SSM.")
        traceback.print_exc()
    finally:
        return configuration


def lambda_handler(event, context):
    """Main handler for function."""
    logger.info("Message received.")

    config = get_config(full_config_path)
    for record in event['Records']:
        try:
            parsed_body = json.loads(record['body'])
        except json.decoder.JSONDecodeError:
            parsed_body = record['body']

        attributes = record['messageAttributes']
        service, outcome, message, object_type, object_status, object_id = parse_attributes(attributes)

        if outcome == 'failure':
            facts = {
                'Service': service,
                'Outcome': outcome,
                'Object Type': object_type,
                'Object Status': object_status,
            }
            if object_id:
                facts["Object ID"] = object_id
            structured_message = structure_teams_message(
                message,
                parsed_body,
                facts)
            decrypted_url = config.get('TEAMS_URL')
            send_teams_message(structured_message, decrypted_url)
