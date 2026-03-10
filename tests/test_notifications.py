#!/usr/bin/env python3

import json
from pathlib import Path
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.handle_data_notifications import (get_config, lambda_handler,
                                           structure_teams_message)


@patch('src.handle_data_notifications.structure_teams_message')
@patch('src.handle_data_notifications.get_config')
@patch('src.handle_data_notifications.send_teams_message')
def test_success_notification(mock_send, mock_config, mock_structure):
    """testing success notifications do not send Teams messages"""
    with open(Path('tests', 'fixtures', 'success_message.json'), 'r') as jf:
        message = json.load(jf)
        lambda_handler(message, None)
        mock_structure.assert_not_called()
        mock_config.assert_called_once()
        mock_send.assert_not_called()


@patch('src.handle_data_notifications.structure_teams_message')
@patch('src.handle_data_notifications.get_config')
@patch('src.handle_data_notifications.send_teams_message')
def test_failure_notification(mock_send, mock_config, mock_structure):
    with open(Path('tests', 'fixtures', 'failure_message.json'), 'r') as jf:
        message = json.load(jf)
        lambda_handler(message, None)
        mock_structure.assert_called_once_with(
            'attention',
            'package 20f8da26e268418ead4aa2365f816a08 failed validation.',
            'BagIt validation failed.',
            'Much longer traceback.',
            {
                'Service': 'validation',
                'Outcome': 'failure',
                'RefID': '20f8da26e268418ead4aa2365f816a08'
            }
        )
        mock_config.assert_called_once()
        mock_send.assert_called_once()


def test_structure_teams_message():
    args = ['attention',
            'package 20f8da26e268418ead4aa2365f816a08 failed validation.',
            'BagIt validation failed.',
            'Much longer traceback.',
            {
                'Service': 'validation',
                'Outcome': 'failure',
                'RefID': '20f8da26e268418ead4aa2365f816a08'
            }]
    with open(Path('tests', 'fixtures', 'failure_message_out.json'), 'r') as df:
        expected = json.load(df)
        output = structure_teams_message(*args)
        assert output == json.dumps(expected)


@mock_aws
def test_config():
    ssm = boto3.client('ssm', region_name='us-east-1')
    path = "/dev/digitized_av_trigger"
    for name, value in [("foo", "bar"), ("baz", "buzz")]:
        ssm.put_parameter(
            Name=f"{path}/{name}",
            Value=value,
            Type="SecureString",
        )
    config = get_config(path)
    assert config == {'foo': 'bar', 'baz': 'buzz'}
