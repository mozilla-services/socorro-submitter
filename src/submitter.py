#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import contextlib
from email.header import Header
import io
import json
import logging
import logging.config
import os
import random
import re
import time

import boto3
from botocore.client import Config as Boto3Config
import requests
import six


NOVALUE = object()


logging.config.dictConfig(
    {
        "version": 1,
        # NOTE(willkg): We don't disable existing loggers because that prevents
        # scripts that use this module from disabling logging.
        "formatters": {
            "mozlog": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": "socorrosubmitter",
            }
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "mozlog",
            }
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
        "loggers": {
            "submitter": {"propagate": False, "handlers": ["console"], "level": "DEBUG"}
        },
    }
)


logger = logging.getLogger("submitter")
logger.setLevel(logging.DEBUG)


class Config(object):
    def __init__(self):
        self.env_name = self.get_from_env("ENV_NAME", "")
        self.throttle = int(self.get_from_env("THROTTLE", "10"))
        self.destination_url = self.get_from_env("DESTINATION_URL")
        self.s3_bucket = self.get_from_env("S3_BUCKET")
        self.s3_region_name = self.get_from_env("S3_REGION_NAME")

        # These are only used for local development
        self.s3_access_key = self.get_from_env("S3_ACCESS_KEY", "")
        self.s3_secret_access_key = self.get_from_env("S3_SECRET_ACCESS_KEY", "")
        self.s3_endpoint_url = self.get_from_env("S3_ENDPOINT_URL", "")

    def get_from_env(self, key, default=NOVALUE):
        if default is NOVALUE:
            return os.environ["SUBMITTER_%s" % key]
        else:
            return os.environ.get("SUBMITTER_%s" % key, default)

    @contextlib.contextmanager
    def override(self, **kwargs):
        """Context-manager in tests to override config variables

        Pass variable (lowercase) = value as args.

        """
        old_values = {}

        for key, val in kwargs.items():
            if getattr(self, key, None) is not None:
                old_values[key] = getattr(self, key)
                setattr(self, key, val)

        yield

        for key, val in old_values.items():
            setattr(self, key, val)


CONFIG = Config()


def statsd_incr(key, value=1, tags=None):
    """Sends a specially formatted line for datadog to pick up for statsd incr"""
    if CONFIG.env_name:
        tags = "#env:%s" % CONFIG.env_name
    else:
        tags = ""

    print(
        "MONITORING|%(timestamp)s|%(val)s|count|%(key)s|%(tags)s"
        % {"timestamp": int(time.time()), "key": key, "val": value, "tags": tags}
    )


CRASH_ID_RE = re.compile(
    r"""
    ^
    [a-f0-9]{8}-
    [a-f0-9]{4}-
    [a-f0-9]{4}-
    [a-f0-9]{4}-
    [a-f0-9]{6}
    [0-9]{6}      # date in YYMMDD
    $
    """,
    re.VERBOSE,
)


def is_crash_id(crash_id):
    """Verifies a given string is a crash id

    :arg str crash_id: the string in question

    :returns: True if it's a crash id and False if not

    """
    return bool(CRASH_ID_RE.match(crash_id))


def extract_crash_id_from_record(record):
    """Given an event record, extracts the crash id

    :arg dict record: the AWS event record

    :returns: None (not a crash id) or the crash_id

    """
    key = "not extracted yet"
    try:
        key = record["s3"]["object"]["key"]
        logger.info("looking at key: %s", key)
        if not key.startswith("v1/processed_crash/"):
            logger.debug("%s: not a processed crash--ignoring", repr(key))
            return None
        crash_id = key.rsplit("/", 1)[-1]
        if not is_crash_id(crash_id):
            logger.debug("%s: not a crash id--ignoring", repr(key))
            return None
        return crash_id
    except (KeyError, IndexError) as exc:
        logger.debug(
            "%s: exception thrown when extracting crashid--ignoring: %s", repr(key), exc
        )
        return None


def get_antenna_throttle_result(crash_id):
    return crash_id[-7]


def build_s3_client(access_key, secret_access_key, region_name=None, endpoint_url=None):
    session_kwargs = {}
    if access_key and secret_access_key:
        session_kwargs["aws_access_key_id"] = access_key
        session_kwargs["aws_secret_access_key"] = secret_access_key
    session = boto3.session.Session(**session_kwargs)

    kwargs = {
        "service_name": "s3",
        "config": Boto3Config(s3={"addressing_style": "path"}),
    }
    if region_name:
        kwargs["region_name"] = region_name

    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    return session.client(**kwargs)


def s3_fetch(client, bucket, key):
    """Fetches a key from S3

    :arg client: S3 client
    :arg bucket: S3 bucket name
    :arg key: key for the item to fetch

    :returns: item as bytes

    """
    data = io.BytesIO()
    client.download_fileobj(bucket, key, data)
    return data.getvalue()


def generate_s3_key(kind, crash_id):
    """Generates the key in S3 for this object kind

    :arg kind: the kind of thing to fetch
    :arg crash_id: the crash id

    :returns: the key name

    """
    if kind == "raw_crash":
        return "v2/raw_crash/%s/20%s/%s" % (crash_id[0:3], crash_id[-6:], crash_id)
    if kind == "dump_names":
        return "v1/dump_names/%s" % crash_id
    if kind in (None, "", "upload_file_minidump"):
        kind = "dump"
    return "v1/%s/%s" % (kind, crash_id)


def fetch_raw_crash(client, bucket, crash_id):
    """Fetches raw crash and converts from JSON to Python dict"""
    key = generate_s3_key("raw_crash", crash_id)
    data = s3_fetch(client, bucket, key).decode("utf-8")
    return json.loads(data)


def fetch_dumps(client, bucket, crash_id):
    """Fetches dump data and returns list of (name, data) tuples"""
    dumps = {}

    # fetch dump_names
    key = generate_s3_key("dump_names", crash_id)
    dump_names = json.loads(s3_fetch(client, bucket, key))

    # fetch dumps
    for name in dump_names:
        key = generate_s3_key(name, crash_id)
        dumps[name] = s3_fetch(client, bucket, key)

    return dumps


def smart_bytes(thing):
    """This converts things to a string representation then to bytes"""
    if isinstance(thing, six.binary_type):
        return thing

    if isinstance(thing, six.string_types):
        return thing.encode("utf-8")

    return repr(thing).encode("utf-8")


def multipart_encode(raw_crash, dumps):
    """Takes a raw_crash and list of (name, dump) and converts to a multipart/form-data

    This returns a tuple of two things:

    1. a ``bytes`` object with the HTTP POST payload
    2. a dict of headers with ``Content-Type`` and ``Content-Length`` in it

    :arg payload_dict: Python dict of name -> value pairs. Values must be either
         strings or a tuple of (filename, file-like objects with ``.read()``).

    :returns: tuple of (bytes, headers dict)

    """
    # NOTE(willkg): This is the result of uuid.uuid4().hex. We just need a
    # unique string to denote the boundary between parts in the payload.
    boundary = "01659896d5dc42cabd7f3d8a3dcdd3bb"
    output = io.BytesIO()

    # Package up raw crash metadata--sort them so they're stable in the payload
    for key, val in sorted(raw_crash.items()):
        output.write(smart_bytes("--%s\r\n" % boundary))
        output.write(
            smart_bytes(
                'Content-Disposition: form-data; name="%s"\r\n' % Header(key).encode()
            )
        )
        output.write(b"Content-Type: text/plain; charset=utf-8\r\n")
        output.write(b"\r\n")
        output.write(smart_bytes(val))
        output.write(b"\r\n")

    # Insert dump data--sort them so they're stable in the payload
    for name, data in sorted(dumps.items()):
        output.write(smart_bytes("--%s\r\n" % boundary))

        # dumps are sent as streams
        output.write(
            smart_bytes(
                'Content-Disposition: form-data; name="%s"; filename="file.dump"\r\n'
                % Header(name).encode()
            )
        )
        output.write(b"Content-Type: application/octet-stream\r\n")
        output.write(b"\r\n")
        output.write(data)
        output.write(b"\r\n")

    # Add end boundary
    output.write(("--%s--\r\n" % boundary).encode("utf-8"))
    output = output.getvalue()

    # Generate headers
    headers = {
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
        "Content-Length": str(len(output)),
    }

    return output, headers


def handler(event, context):
    accepted_records = []

    logger.info("number of records: %d", len(event["Records"]))
    for record in event["Records"]:
        # Skip anything that's not an S3 ObjectCreated:put event
        if (
            record["eventSource"] != "aws:s3"
            or record["eventName"] != "ObjectCreated:Put"
        ):
            continue

        # Extract bucket name for debugging
        bucket = record["s3"]["bucket"]["name"]

        # Extract crash id--if it's not a processed crash object, skip it.
        crash_id = extract_crash_id_from_record(record)
        if crash_id is None:
            continue

        logger.debug("saw crash id: %s in %s", crash_id, bucket)

        # Throttle crashes
        if CONFIG.throttle < 100 and random.randint(0, 100) > CONFIG.throttle:
            statsd_incr("socorro.submitter.throttled", value=1)
            continue

        accepted_records.append(crash_id)

    # If we don't have anything to post, we're done!
    if not accepted_records:
        return

    for crash_id in accepted_records:
        try:
            statsd_incr("socorro.submitter.accept", value=1)

            # Build client
            client = build_s3_client(
                access_key=CONFIG.s3_access_key,
                secret_access_key=CONFIG.s3_secret_access_key,
                region_name=CONFIG.s3_region_name,
                endpoint_url=CONFIG.s3_endpoint_url,
            )

            # Fetch raw crash data from S3
            raw_crash = fetch_raw_crash(client, CONFIG.s3_bucket, crash_id)
            dumps = fetch_dumps(client, CONFIG.s3_bucket, crash_id)

        except Exception:
            statsd_incr("socorro.submitter.unknown_s3fetch_error", value=1)
            logger.exception("Error: s3 fetch failed for unknown reason: %s", crash_id)
            raise

        try:
            # Assemble payload and headers
            payload, headers = multipart_encode(raw_crash, dumps)

            # POST crash to new environment
            requests.post(CONFIG.destination_url, headers=headers, data=payload)

        except Exception:
            statsd_incr("socorro.submitter.unknown_httppost_error", value=1)
            logger.exception("Error: http post failed for unknown reason: %s", crash_id)
            raise
