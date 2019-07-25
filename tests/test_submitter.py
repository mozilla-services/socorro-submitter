# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from submitter import CONFIG, extract_crash_id_from_record


def test_basic(client, capsys, fakes3, mock_collector):
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

    # Make sure it doesn't get throttled and invoke the Lambda function
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

    stdout, stderr = capsys.readouterr()
    assert "|1|count|socorro.submitter.accept|" in stdout


def test_multiple_dumps(client, capsys, fakes3, mock_collector):
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

    # Make sure it doesn't get throttled and invoke the Lambda function
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

    stdout, stderr = capsys.readouterr()
    assert "|1|count|socorro.submitter.accept|" in stdout


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


def test_throttle_accepted(client, capsys, mocker, fakes3, mock_collector):
    always_20 = mocker.patch("random.randint")
    always_20.return_value = 20

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

    # Set throttle value above the mocked randint, so this should get submitted
    with CONFIG.override(throttle=30):
        assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    stdout, stderr = capsys.readouterr()
    assert "|1|count|socorro.submitter.accept|" in stdout


def test_throttle_skipped(client, capsys, mocker, fakes3, mock_collector):
    always_20 = mocker.patch("random.randint")
    always_20.return_value = 20

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

    # Set throttle value below the mocked randint, so this should get skipped
    with CONFIG.override(throttle=10):
        assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0

    stdout, stderr = capsys.readouterr()
    assert "|1|count|socorro.submitter.throttled|" in stdout


def test_env_tag_added_to_statds_incr(client, capsys, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "Product": "Firefox",
            "Version": "60.0",
        },
        dumps={"upload_file_minidump": "abcdef"},
    )

    with CONFIG.override(env_name="stage", throttle=100):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        #                                        ^ accept
        events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
        assert client.run(events) is None

        # Verify payload was submitted
        assert len(mock_collector.payloads) == 1

        stdout, stderr = capsys.readouterr()
        assert "|1|count|socorro.submitter.accept|#env:stage\n" in stdout


@pytest.mark.parametrize(
    "data, expected",
    [
        # Raw crash file
        (
            "v2/raw_crash/de1/20160918/de1bb258-cbbf-4589-a673-34f800160918",
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
