#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
from email.header import Header
import gzip
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
import dockerflow  # noqa
from google.cloud.logging_v2.client import Client as CloudLoggingClient
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers.transports.sync import SyncTransport
from google.oauth2.service_account import Credentials
import requests


NOVALUE = object()


class Config:
    def __init__(self):
        self.env_name = self.get_from_env("ENV_NAME", "")
        self.throttle = int(self.get_from_env("THROTTLE", "10"))
        self.destination_url = self.get_from_env("DESTINATION_URL")
        self.s3_bucket = self.get_from_env("S3_BUCKET")
        self.s3_region_name = self.get_from_env("S3_REGION_NAME")

        # For GCP stackdriver logging
        self.gcp_credentials = self.get_from_env("GCP_CREDENTIALS", "")

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

LOGGER_NAME = "submitter"


def setup_logging(config):
    logging_config = {
        "version": 1,
        # NOTE(willkg): We don't disable existing loggers because that prevents
        # scripts that use this module from disabling logging.
        "disable_existing_loggers": False,
        "formatters": {
            "mozlog": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": LOGGER_NAME,
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
        "loggers": {LOGGER_NAME: {"handlers": ["console"], "level": "INFO"}},
    }

    logging.config.dictConfig(logging_config)

    # If a GCP project id is set, then create a logging handler for it and set
    # it up
    if config.gcp_credentials:
        acct_info = json.loads(config.gcp_credentials)
        credentials = Credentials.from_service_account_info(acct_info)
        client = CloudLoggingClient(
            project=acct_info["project_id"], credentials=credentials
        )

        handler = CloudLoggingHandler(
            client=client, name="socorro-stage-submitter", transport=SyncTransport
        )
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)
        logging.getLogger(LOGGER_NAME).addHandler(handler)


setup_logging(CONFIG)
LOGGER = logging.getLogger(LOGGER_NAME)


def statsd_incr(key, value=1, tags=None):
    """Sends a specially formatted line for datadog to pick up for statsd incr"""
    if CONFIG.env_name:
        tags = "#env:%s" % CONFIG.env_name
    else:
        tags = ""

    # We pass the data in the message and in extra because mozlog will add
    # extra fields to its JSON msg
    msg = "MONITORING|%(timestamp)s|%(value)s|count|%(key)s|%(tags)s" % {
        "timestamp": int(time.time()),
        "key": key,
        "value": value,
        "tags": tags,
    }
    LOGGER.info(msg, extra={"key": key, "value": value, "tags": tags})


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
        LOGGER.debug("looking at key: %s", key)
        if not key.startswith("v1/raw_crash/"):
            LOGGER.debug("%s: not a raw crash--ignoring", repr(key))
            return None
        crash_id = key.rsplit("/", 3)[-1]
        if not is_crash_id(crash_id):
            LOGGER.debug("%s: not a crash id--ignoring", repr(key))
            return None
        return crash_id
    except (KeyError, IndexError):
        LOGGER.exception(
            "%s: exception thrown when extracting crashid--ignoring", repr(key)
        )
        return None


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
        return "v1/raw_crash/20%s/%s" % (crash_id[-6:], crash_id)
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


COLLECTOR_KEYS_TO_REMOVE = [
    "metadata",
    "submitted_timestamp",
    "version",
]


def remove_collector_keys(raw_crash):
    """Given a raw crash, removes keys added by a collector

    :arg raw_crash: dict of annotations and collector-added data

    :returns: raw_crash

    """
    for key in COLLECTOR_KEYS_TO_REMOVE:
        if key in raw_crash:
            del raw_crash[key]

    return raw_crash


def smart_bytes(thing):
    """This converts things to a string representation then to bytes"""
    if isinstance(thing, bytes):
        return thing

    if isinstance(thing, str):
        return thing.encode("utf-8")

    return repr(thing).encode("utf-8")


def multipart_encode(raw_crash, dumps, payload_type, payload_compressed):
    """Takes a raw_crash and list of (name, dump) and converts to a multipart/form-data

    This returns a tuple of two things:

    1. a ``bytes`` object with the HTTP POST payload
    2. a dict of headers with ``Content-Type`` and ``Content-Length`` in it

    :arg raw_crash: dict of crash annotations
    :arg dumps: list of (name, dump) tuples
    :arg payload_type: either "multipart" or "json"
    :arg payload_compressed: either "1" or "0"

    :returns: tuple of (bytes, headers dict)

    """
    # NOTE(willkg): This is the result of uuid.uuid4().hex. We just need a
    # unique string to denote the boundary between parts in the payload.
    boundary = "01659896d5dc42cabd7f3d8a3dcdd3bb"
    output = io.BytesIO()

    # If the payload of the original crash report had the crash annotations in
    # the "extra" field as a JSON blob, we should do the same here
    if payload_type == "json":
        output.write(smart_bytes("--%s\r\n" % boundary))
        output.write(b'Content-Disposition: form-data; name="extra"\r\n')
        output.write(b"Content-Type: application/json\r\n")
        output.write(b"\r\n")
        extra_data = json.dumps(raw_crash, sort_keys=True, separators=(",", ":"))
        output.write(smart_bytes(extra_data))
        output.write(b"\r\n")

    else:
        # Package up raw crash metadata--sort them so they're stable in the payload
        for key, val in sorted(raw_crash.items()):
            output.write(smart_bytes("--%s\r\n" % boundary))
            output.write(
                smart_bytes(
                    'Content-Disposition: form-data; name="%s"\r\n'
                    % Header(key).encode()
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

    # Compress if it we need to
    if payload_compressed == "1":
        bio = io.BytesIO()
        g = gzip.GzipFile(fileobj=bio, mode="w")
        g.write(output)
        g.close()
        output = bio.getbuffer()
        headers["Content-Length"] = str(len(output))
        headers["Content-Encoding"] = "gzip"

    return output, headers


def get_payload_type(raw_crash):
    if raw_crash.get("metadata", {}).get("payload") is not None:
        return raw_crash["metadata"]["payload"]

    return "unknown"


def get_payload_compressed(raw_crash):
    if raw_crash.get("metadata", {}).get("payload_compressed") is not None:
        return raw_crash["metadata"]["payload_compressed"]

    return "0"


def handler(event, context):
    accepted_records = []

    LOGGER.debug("number of records: %d", len(event["Records"]))
    for record in event["Records"]:
        # Skip anything that's not an S3 ObjectCreated:put event
        if (
            record["eventSource"] != "aws:s3"
            or record["eventName"] != "ObjectCreated:Put"
        ):
            continue

        # Extract bucket name for debugging
        bucket = record["s3"]["bucket"]["name"]

        # Extract crash id--if it's not a raw crash object, skip it.
        crash_id = extract_crash_id_from_record(record)
        if crash_id is None:
            continue

        LOGGER.debug("saw crash id: %s in %s", crash_id, bucket)

        # Throttle crashes
        if CONFIG.throttle < 100 and random.randint(0, 100) > CONFIG.throttle:
            LOGGER.info("submitted: %s", crash_id)
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

            payload_type = get_payload_type(raw_crash)
            payload_compressed = get_payload_compressed(raw_crash)

            # Remove keys created by the collector from the raw crash
            raw_crash = remove_collector_keys(raw_crash)

        except Exception:
            statsd_incr("socorro.submitter.unknown_s3fetch_error", value=1)
            LOGGER.exception("Error: s3 fetch failed for unknown reason: %s", crash_id)
            raise

        try:
            # Assemble payload and headers
            payload, headers = multipart_encode(
                raw_crash=raw_crash,
                dumps=dumps,
                payload_type=payload_type,
                payload_compressed=payload_compressed,
            )

            # POST crash to new environment
            requests.post(CONFIG.destination_url, headers=headers, data=payload)

        except Exception:
            statsd_incr("socorro.submitter.unknown_httppost_error", value=1)
            LOGGER.exception("Error: http post failed for unknown reason: %s", crash_id)
            raise
