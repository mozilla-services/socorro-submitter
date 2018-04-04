#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# This runs an integration test by invoking Submitter with a series of
# keys and then checking the queue to see what got posted.

set -e

# First, empty the queues quietly.
(docker-compose run test ./bin/consume_queue.py) 2>&1 > /dev/null

# Second post a bunch of keys.
# accepted raw crash
./bin/generate_event.py --key v2/raw_crash/000/20180313/00007bd0-2d1c-4865-af09-80bc00180313 | ./bin/run_invoke.sh

# defered raw crash
./bin/generate_event.py --key v2/raw_crash/111/20180313/11107bd0-2d1c-4865-af09-80bc01180313 | ./bin/run_invoke.sh

# dump_names
./bin/generate_event.py --key v1/dump_names/00007bd0-2d1c-4865-af09-80bc01180313 | ./bin/run_invoke.sh

# dump
./bin/generate_event.py --key v1/dump/00007bd0-2d1c-4865-af09-80bc01180313 | ./bin/run_invoke.sh

# junk
./bin/generate_event.py --key junk | ./bin/run_invoke.sh

# Check the queue
EXPECTED="item: 00007bd0-2d1c-4865-af09-80bc00180313"

OUTPUT=$((docker-compose run test ./bin/consume_queue.py) | grep "^item: " | sed 's/\s*$//' )

if [ "${OUTPUT}" == "${EXPECTED}" ]; then
    echo "SUCCESS: Integration test passed!"
else
    echo "FAIL: Integration test failed. Output of queues:"
    echo "--${OUTPUT}--"
    exit 1
fi
