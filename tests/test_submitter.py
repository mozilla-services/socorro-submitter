# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from submitter import CONFIG, extract_crash_id_from_record


def test_basic(client, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'Product': 'Firefox',
            'Version': '60.0',
        },
        dumps={
            'upload_file_minidump': 'abcdef'
        }
    )

    crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
    assert client.run(events) is None

    # Verify payload was submitted
    assert len(mock_collector.payloads) == 1
    post_payload = mock_collector.payloads[0].text

    # Who doesn't like reading raw multipart/form-data? Woo hoo!
    assert (
        post_payload ==
        '--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n'
        'Content-Disposition: form-data; name="Product"\r\n'
        'Content-Type: text/plain; charset=utf-8\r\n'
        '\r\n'
        '\r\n'
        'Firefox--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n'
        'Content-Disposition: form-data; name="Version"\r\n'
        'Content-Type: text/plain; charset=utf-8\r\n'
        '\r\n'
        '\r\n'
        '60.0--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n'
        'Content-Disposition: form-data; name="uuid"\r\n'
        'Content-Type: text/plain; charset=utf-8\r\n'
        '\r\n'
        '\r\n'
        'de1bb258-cbbf-4589-a673-34f800160918--01659896d5dc42cabd7f3d8a3dcdd3bb\r\n'
        'Content-Disposition: form-data; name="uuid"; filename="upload_file_minidump"\r\n'
        'Content-Type: application/octet-stream\r\n'
        '\r\n'
        '\r\n'
        'abcdef\r\n'
        '--01659896d5dc42cabd7f3d8a3dcdd3bb--\r\n'
    )


def test_non_s3_event(client, fakes3, mock_collector):
    events = {
        'Records': [
            {
                'eventSource': 'aws:lonnen',
            }
        ]
    }
    assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0


def test_non_put_event(client, fakes3, mock_collector):
    events = {
        'Records': [
            {
                'eventSource': 'aws:lonnen',
            }
        ]
    }
    assert client.run(events) is None

    # Verify no payload was submitted
    assert len(mock_collector.payloads) == 0


def test_env_tag(client, capsys, fakes3, mock_collector):
    fakes3.create_bucket()
    fakes3.save_crash(
        raw_crash={
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'Product': 'Firefox',
            'Version': '60.0',
        },
        dumps={
            'upload_file_minidump': 'abcdef'
        }
    )

    with CONFIG.override(env_name='stage'):
        crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
        #                                        ^ accept
        events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
        assert client.run(events) is None

        # Verify payload was submitted
        assert len(mock_collector.payloads) == 1

        stdout, stderr = capsys.readouterr()
        assert '|1|count|socorro.submitter.accept|#env:stage\n' in stdout


def test_defer(client, capsys, fakes3, mock_collector):
    crash_id = 'de1bb258-cbbf-4589-a673-34f801160918'
    #                                        ^ defer
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
    assert client.run(events) is None

    # FIXME(willkg): Verify no payload was submitted

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.defer|' in stdout


def test_accept(client, capsys):
    crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
    #                                        ^ accept
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
    assert client.run(events) is None

    # FIXME(willkg): Verify payload was submitted

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.accept|' in stdout


def test_invalid_instruction(client, capsys):
    crash_id = 'de1bb258-cbbf-4589-a673-34f802160918'
    #                                        ^ not accept or defer
    events = client.build_crash_save_events(client.crash_id_to_key(crash_id))
    assert client.run(events) is None

    # FIXME(willkg): Verify no payload was submitted

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.junk|' in stdout


@pytest.mark.parametrize('data, expected', [
    # Raw crash file
    (
        'v2/raw_crash/de1/20160918/de1bb258-cbbf-4589-a673-34f800160918',
        'de1bb258-cbbf-4589-a673-34f800160918'
    ),

    # Other files that get saved in the same bucket
    ('v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918', None),
    ('v1/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918', None),

    # Test-like files we might have pushed places to make sure things are working
    ('v2/raw_crash/de1/20160918/test', None),
    ('foo/bar/test', None),

    # Junk in accept/defer position
    ('v2/raw_crash/edd/20170404/edd0cf02-9e6f-443a-b098-8274b2170404', None),
])
def test_extract_crash_id_from_record(data, expected, client):
    record = client.build_crash_save_events(data)['Records'][0]
    assert extract_crash_id_from_record(record) == expected
