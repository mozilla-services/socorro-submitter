# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import gzip
import logging
import random

import pytest

from submitter import (
    CONFIG,
    extract_crash_id_from_record,
    get_payload_type,
    get_payload_compressed,
    remove_collector_keys,
)


@pytest.mark.parametrize(
    "raw_crash, expected",
    [
        ({}, "unknown"),
        ({"metadata": {"payload": "json"}}, "json"),
    ],
)
def test_get_payload_type(raw_crash, expected):
    assert get_payload_type(raw_crash) == expected


@pytest.mark.parametrize(
    "raw_crash, expected",
    [
        ({}, "0"),
        ({"metadata": {"payload_compressed": "1"}}, "1"),
    ],
)
def test_get_payload_compressed(raw_crash, expected):
    assert get_payload_compressed(raw_crash) == expected


@pytest.mark.parametrize(
    "raw_crash, expected",
    [
        ({}, {}),
        (
            {
                "Product": "Firefox",
                "Version": "60.0",
                "metadata": {
                    "collector_notes": [],
                    "dump_checksums": {},
                    "payload_compressed": "0",
                    "payload": "multipart",
                },
                "version": 2,
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "submitted_timestamp": "2022-09-14T15:45:55.222222",
            },
            {
                "Product": "Firefox",
                "Version": "60.0",
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            },
        ),
    ],
)
def test_remove_collector_keys(raw_crash, expected):
    assert remove_collector_keys(raw_crash) == expected


def test_basic(client, caplog, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "Product": "Firefox",
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Version": "60.0",
            "metadata": {
                "collector_notes": [],
                "dump_checksums": {},
                "payload_compressed": "0",
                "payload": "multipart",
            },
            "version": 2,
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture logs, make sure it doesn't get throttled, and invoke the Lambda
    # function
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=100):
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    post_payload = mock_collector.payloads[0].text

    # Who doesn't like reading raw multipart/form-data? Woo hoo!
    assert (
        post_payload == "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="Product"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Firefox\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="Version"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "60.0\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="uuid"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "de1bb258-cbbf-4589-a673-34f800160918\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="upload_file_minidump"; filename="file.dump"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
        "abcdef\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb--\r\n"
    )

    assert "|1|count|socorro.submitter.accept|#env:test" in caplog.record_tuples[0][2]


def test_annotations_as_json(client, caplog, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
            "metadata": {
                "payload": "json",
            },
            "version": 2,
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture logs, make sure it doesn't get throttled, and invoke the Lambda
    # function
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=100):
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    post_payload = mock_collector.payloads[0].text

    # Who doesn't like reading raw multipart/form-data? Woo hoo!
    assert (
        post_payload == "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="extra"\r\n'
        "Content-Type: application/json\r\n"
        "\r\n"
        '{"Product":"Firefox","Version":"60.0","uuid":"de1bb258-cbbf-4589-a673-34f800160918"}\r\n'
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="upload_file_minidump"; filename="file.dump"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
        "abcdef\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb--\r\n"
    )

    assert "|1|count|socorro.submitter.accept|#env:test" in caplog.record_tuples[0][2]


def test_multiple_dumps(client, caplog, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
        },
        dumps={
            "upload_file_minidump": "abcdef",
            "upload_file_minidump_content": "abcdef2",
        },
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture logs, make sure it doesn't get throttled, and invoke the Lambda
    # function
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=100):
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    post_payload = mock_collector.payloads[0].text

    # Who doesn't like reading raw multipart/form-data? Woo hoo!
    assert (
        post_payload == "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="Product"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Firefox\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="Version"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "60.0\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="uuid"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "de1bb258-cbbf-4589-a673-34f800160918\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="upload_file_minidump"; filename="file.dump"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
        "abcdef\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        'Content-Disposition: form-data; name="upload_file_minidump_content"; '
        'filename="file.dump"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
        "abcdef2\r\n"
        "--01659896d5dc42cabd7f3d8a3dcdd3bb--\r\n"
    )

    assert "|1|count|socorro.submitter.accept|" in caplog.record_tuples[0][2]


def test_compressed(client, caplog, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
            "metadata": {
                "payload_compressed": "1",
            },
            "version": 2,
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture logs, make sure it doesn't get throttled, and invoke the Lambda
    # function
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=100):
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    req = mock_collector.payloads[0]
    print(repr(req))

    # Assert the header
    assert req.headers["Content-Encoding"] == "gzip"

    # Assert it was accepted
    assert "|1|count|socorro.submitter.accept|#env:test" in caplog.record_tuples[0][2]

    # Assert the length and payload are correct and payload is compressed
    post_payload = req.body
    assert len(post_payload) == int(req.headers["Content-Length"])

    unzipped_payload = gzip.decompress(post_payload)
    assert (
        unzipped_payload == b"--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        b'Content-Disposition: form-data; name="Product"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Firefox\r\n"
        b"--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        b'Content-Disposition: form-data; name="Version"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"60.0\r\n"
        b"--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        b'Content-Disposition: form-data; name="uuid"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"de1bb258-cbbf-4589-a673-34f800160918\r\n"
        b"--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n"
        b'Content-Disposition: form-data; name="upload_file_minidump"; '
        b'filename="file.dump"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        b"abcdef\r\n"
        b"--01659896d5dc42cabd7f3d8a3dcdd3bb--\r\n"
    )


def test_non_s3_event_ignored(client, fakes3, mock_collector):
    events = {
        "Records": [{"eventSource": "aws:lonnen", "eventName": "ObjectCreated:Move"}]
    }
    assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0


def test_non_put_event_ignored(client, fakes3, mock_collector):
    events = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Move"}]}
    assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0


def test_throttle_accepted(client, caplog, monkeypatch, fakes3, mock_collector):
    def always_20(*args, **kwargs):
        return 20

    monkeypatch.setattr(random, "randint", always_20)

    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture the log and set throttle value above the mocked randint--this should
    # get submitted
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=30):
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    assert "|1|count|socorro.submitter.accept|" in caplog.record_tuples[0][2]


def test_throttle_skipped(client, caplog, monkeypatch, fakes3, mock_collector):
    def always_20(*args, **kwargs):
        return 20

    monkeypatch.setattr(random, "randint", always_20)

    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))

    # Capture the logs and set throttle value below the mocked randint--this
    # should get skipped
    with caplog.at_level(logging.INFO):
        with CONFIG.override(throttle=10):
            assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0

    assert "|1|count|socorro.submitter.throttled|" in caplog.record_tuples[1][2]


def test_env_tag_added_to_statds_incr(client, caplog, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    with caplog.at_level(logging.INFO):
        with CONFIG.override(env_name="stage", throttle=100):
            crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
            #                                        ^ accept
            events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
            assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1

    assert "|1|count|socorro.submitter.accept|#env:stage" in caplog.record_tuples[0][2]


@pytest.mark.parametrize(
    "data, expected",
    [
        # Raw crash file
        (
            "v1/raw_crash/20160918/de1bb258-cbbf-4589-a673-34f800160918",
            "de1bb258-cbbf-4589-a673-34f800160918",
        ),
        # Other files that get saved in the same bucket
        ("v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918", None),
        ("v1/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918", None),
        ("v1/processed_crash/de1bb258-cbbf-4589-a673-34f800160918", None),
        # Test-like files we might have pushed places to make sure things are working
        ("v1/processed_crash/test", None),
        ("foo/bar/test", None),
    ],
)
def test_extract_crash_id_from_record(data, expected, client):
    record = client.build_crash_save_events(data)["Records"][0]
    assert extract_crash_id_from_record(record) == expected
