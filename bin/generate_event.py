#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Generates a sample S3 event for testing submitter invocation.
#
# Usage: ./bin/generate_event.py --key=KEY

import argparse
import json
import sys


def make_event(key, event_name='ObjectCreated:Put', bucket='dev_bucket'):
    """Generates an S3 event

    .. Note::

       This only generates enough event boilerplate for submitter.

    """
    return {
        'Records': [
            {
                'eventVersion': '2.0',
                'eventSource': 'aws:s3',
                'eventName': event_name,
                's3': {
                    's3SchemaVersion': '1.0',
                    'object': {
                        'key': key
                    },
                    'bucket': {
                        'arn': 'arn:aws:s3:::' + bucket,
                        'name': bucket,
                        'ownerIdentity': {
                            'principalId': 'submitterrules'
                        }
                    }
                }
            }
        ]
    }


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--eventname', default='ObjectCreated:Put',
        help='the event triggered'
    )
    parser.add_argument(
        '--bucket', default='dev_bucket',
        help='the bucket that generated the event'
    )
    parser.add_argument(
        '--key', default='',
        help='the key for the S3 object that triggered the event'
    )
    args = parser.parse_args(argv)

    event = make_event(key=args.key, event_name=args.eventname, bucket=args.bucket)
    print(json.dumps(event))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
