# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from contextlib import contextmanager
import io
import json
import os
import random
import sys
import uuid

import boto3
from botocore.client import Config as Boto3Config
from moto import mock_s3
import requests_mock
import pytest


# Insert build/ directory in sys.path so we can import submitter
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'build'
    )
)


from submitter import CONFIG, generate_s3_key, handler  # noqa


class LambdaContext:
    """Context class that mimics the AWS Lambda context

    http://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    """
    def __init__(self):
        self.aws_request_id = uuid.uuid4().hex

        self.log_group_name = '/aws/lambda/test'
        self.log_stream_name = '2016-11-15blahblah'

        self.function_name = 'test'
        self.memory_limit_in_mb = '384'
        self.function_version = '1'
        self.invoked_function_arn = 'arn:aws:lambda:us-west-2:blahblah:function:test'

        # FIXME(willkg): Keeping these as None until we need them.
        self.client_context = None
        self.identity = None

    def get_remaining_time_in_millis(self):
        # FIXME(willkg): Implement this when we need it
        return 5000


class SubmitterClient:
    """Class for submitter in the AWS lambda environment"""
    def crash_id_to_key(self, crash_id):
        return 'v2/raw_crash/{entropy}/{date}/{crashid}'.format(
            entropy=crash_id[0:3],
            date='20' + crash_id[-6:],
            crashid=crash_id
        )

    def build_crash_save_events(self, keys):
        if isinstance(keys, str):
            keys = [keys]

        # FIXME(willkg): This only generates a record that has the stuff that
        # submitter is looking for. It's not a full record.
        return {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'object': {
                            'key': key
                        },
                        'bucket': {
                            'name': 'dev_bucket'
                        }
                    }
                }
                for key in keys
            ]
        }

    def run(self, events):
        result = handler(events, LambdaContext())
        return result


@pytest.fixture
def client():
    """Returns an AWS Lambda mock that runs submitter thing"""
    return SubmitterClient()


@pytest.yield_fixture
def mock_randint_always_20():
    """Mocks random.randint to always return 20"""
    old_randint = random.randint

    def mock_randint(a, b):
        print('MOCKED RANDINT')
        return 20

    random.randint = mock_randint
    yield
    random.randint = old_randint


class FakeCollector(object):
    """Fakes a collector that the submitter submits to

    :attribute payloads: the list of payloads that was received since this was
        created or the last time ``.clear()`` was called

    """
    def __init__(self):
        self.payloads = []

    def clear(self):
        self.payloads = []

    def handle_post(self, request, context):
        self.payloads.append(request)
        context.status = 200
        # FIXME(willkg): this should return the same crash id that it got--but
        # that requires parsing the payload. :(
        crashid = 'xxx'
        return 'CrashID=bp-%s' % crashid

    @contextmanager
    def setup_mock(self):
        with requests_mock.mock() as rm:
            rm.post(
                '//fakecollector:8000/submit',
                text=self.handle_post,
            )
            yield self


@pytest.yield_fixture
def mock_collector():
    """Creates a mock collector that lets you observe posted payloads"""
    with FakeCollector().setup_mock() as fm:
        yield fm


class FakeS3(object):
    """Convenience class for manipulating S3 for test setup"""
    def jsonify(self, data):
        return json.dumps(data, sort_keys=True)

    def build_s3_client(self):
        session = boto3.session.Session()
        return session.client(
            service_name='s3',
            config=Boto3Config(s3={'addressing_style': 'path'})
        )

    def create_bucket(self):
        """Gets or creates the S3 bucket specified in ``CONFIG.s3_bucket``"""
        bucket = CONFIG.s3_bucket
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(bucket)
        bucket.create()

    def upload_file(self, key, data):
        client = self.build_s3_client()
        print('upload_file', CONFIG.s3_bucket, key, data)

        client.upload_fileobj(
            Fileobj=io.BytesIO(data),
            Bucket=CONFIG.s3_bucket,
            Key=key
        )

    def save_crash(self, raw_crash, dumps):
        """Saves crash data to S3

        :arg raw_crash: dict specifying the raw crash
        :arg dumps: dict of dump name -> dump data

        """
        crash_id = raw_crash['uuid']

        # Save raw crash
        key = generate_s3_key('raw_crash', crash_id)
        data = self.jsonify(raw_crash).encode('utf-8')
        self.upload_file(key, data)

        # Save dump_names
        key = generate_s3_key('dump_names', crash_id)
        data = self.jsonify(list(dumps.keys())).encode('utf-8')
        self.upload_file(key, data)

        # Save dumps
        for name, data in dumps.items():
            key = generate_s3_key(name, crash_id)
            data = data.encode('utf-8')
            self.upload_file(key, data)


@pytest.yield_fixture
def fakes3():
    """Sets up mock S3 and returns a convenience class"""
    # Mock out AWS S3
    with mock_s3():
        # Fix config to use regular AWS so it's mocked
        s3_vars = {
            's3_access_key': '',
            's3_secret_access_key': '',
            's3_endpoint_url': '',
            's3_region': ''
        }
        with CONFIG.override(**s3_vars):
            # Yield a FakeS3 client for test convenience
            yield FakeS3()
