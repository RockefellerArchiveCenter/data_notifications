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
def test_failure_notification_fetch(mock_send, mock_config, mock_structure):
    with open(Path('tests', 'fixtures', 'failure_message_fetch.json'), 'r') as jf:
        message = json.load(jf)
        lambda_handler(message, None)
        mock_structure.assert_called_once_with(
            'fetch for updated archival objects failed.',
            'fetch failed.',
            {
                'Service': "data_fetch",
                'Outcome': "failure",
                'Object Type': "archival object",
                'Object Status': "updated",
            }
        )
        mock_config.assert_called_once()
        mock_send.assert_called_once()


@patch('src.handle_data_notifications.structure_teams_message')
@patch('src.handle_data_notifications.get_config')
@patch('src.handle_data_notifications.send_teams_message')
def test_failure_notification_object(mock_send, mock_config, mock_structure):
    with open(Path('tests', 'fixtures', 'failure_message_merge.json'), 'r') as jf:
        message = json.load(jf)
        lambda_handler(message, None)
        mock_structure.assert_called_once_with(
            'merging archival objects failed.',
            'merge failed.',
            {
                'Service': "data_merge",
                'Outcome': "failure",
                'Object Type': "archival object",
                'Object Status': "updated",
                'Object ID': "asdklfjalks"
            }
        )
        mock_config.assert_called_once()
        mock_send.assert_called_once()


def test_structure_teams_message():
    args = ['fetch for updated archival objects failed.',
            'fetch failed.',
            {
                'Service': "data_fetch",
                'Outcome': "FAILURE",
                'Object Type': "archival object",
                'Object Status': "updated",
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
