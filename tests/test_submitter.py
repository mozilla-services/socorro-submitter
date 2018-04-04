# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from submitter import CONFIG, extract_crash_id_from_record


def test_basic(client):
    crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
    events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
    assert client.run(events) is None

    # item = rabbitmq_helper.next_item()
    # assert item == crash_id


def test_non_s3_event(client):
    events = {
        'Records': [
            {
                'eventSource': 'aws:lonnen',
            }
        ]
    }
    assert client.run(events) is None

    # Verify that no rabbit message got created
    # item = rabbitmq_helper.next_item()
    # assert item is None


def test_non_put_event(client):
    events = {
        'Records': [
            {
                'eventSource': 'aws:lonnen',
            }
        ]
    }
    assert client.run(events) is None

    # Verify that no rabbit message got created
    # item = rabbitmq_helper.next_item()
    # assert item is None


def test_env_tag(client, capsys):
    with CONFIG.override(env='stage'):
        crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
        #                                        ^ accept
        events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
        assert client.run(events) is None

        # item = rabbitmq_helper.next_item()
        # assert item == crash_id

        stdout, stderr = capsys.readouterr()
        assert '|1|count|socorro.submitter.accept|#env:stage\n' in stdout


def test_defer(client, rabbitmq_helper, capsys):
    crash_id = 'de1bb258-cbbf-4589-a673-34f801160918'
    #                                        ^ defer
    events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
    assert client.run(events) is None

    # item = rabbitmq_helper.next_item()
    # assert item is None

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.defer|' in stdout


def test_accept(client, rabbitmq_helper, capsys):
    crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
    #                                        ^ accept
    events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
    assert client.run(events) is None

    # item = rabbitmq_helper.next_item()
    # assert item == crash_id

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.accept|' in stdout


def test_junk(client, rabbitmq_helper, capsys):
    crash_id = 'de1bb258-cbbf-4589-a673-34f802160918'
    #                                        ^ junk
    events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
    assert client.run(events) is None

    # item = rabbitmq_helper.next_item()
    # assert item is None

    stdout, stderr = capsys.readouterr()
    assert '|1|count|socorro.submitter.junk|' in stdout


def test_junk_in_stage(client, rabbitmq_helper, capsys):
    with CONFIG.override(env='stage'):
        crash_id = 'de1bb258-cbbf-4589-a673-34f802160918'
        #                                        ^ junk
        events = client.build_crash_save_events(client.crash_id_to_path(crash_id))
        assert client.run(events) is None

        # item = rabbitmq_helper.next_item()
        # assert item == crash_id

        stdout, stderr = capsys.readouterr()
        assert '|1|count|socorro.submitter.accept|' in stdout


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
