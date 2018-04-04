# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import random
import sys
import uuid

import pytest


# Insert build/ directory in sys.path so we can import submitter
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'build'
    )
)


from submitter import CONFIG, handler  # noqa


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
    def crash_id_to_path(self, crash_id):
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
