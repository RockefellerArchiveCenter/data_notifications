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
    color_name = 'attention' if attributes['outcome']['Value'] == 'FAILURE' else 'good'
    refid = attributes.get('refid', {}).get('Value', None)
    service = attributes['service']['Value']
    outcome = attributes['outcome']['Value'].lower()
    message = attributes.get('message', {}).get('Value')
    traceback = attributes.get('traceback', {}).get('Value')
    return color_name, refid, service, outcome, message, traceback


def structure_teams_message(color_name, title, message, traceback, facts):
    """Structures Teams message using arguments."""
    body = [
        {
            "type": "TextBlock",
                    "size": "default",
                    "weight": "bolder",
                    "text": title,
                    "style": "heading",
                    "wrap": True,
                    "color": color_name
        },
        {
            "type": "TextBlock",
                    "text": message,
                    "wrap": True
        },

    ]
    if facts['RefID']:
        body.append(
            {
                "type": "FactSet",
                "facts": [{"title": k, "value": v} for k, v in facts.items()]
            }
        )
    if traceback:
        body.append({
            "type": "TextBlock",
            "fontType": "Monospace",
            "text": traceback,
            "wrap": True
        })
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
        title = record['Sns']['Message']
        attributes = record['Sns']['MessageAttributes']
        color_name, refid, service, outcome, message, traceback = parse_attributes(attributes)
        if outcome == 'failure':
            structured_message = structure_teams_message(
                color_name,
                title,
                message,
                traceback,
                {
                    'Service': service,
                    'Outcome': outcome,
                    'RefID': refid
                })
            decrypted_url = config.get('TEAMS_URL')
            send_teams_message(structured_message, decrypted_url)
