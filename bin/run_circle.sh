#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Runs flake8 and unit tests in the test container. This is used by
# Circle CI.
#
# Note: Circle CI's Docker can't mount volumes, so we have to run docker
# rather than docker-compose to get around that.
#
# Usage: ./bin/run_circle.sh

docker-compose up -d rabbitmq
docker network ls

# Run flake8
docker run \
    --rm \
    --workdir=/app \
    --env-file=docker/lambda.env \
    socorrosubmitter_test flake8 /app/build/submitter.py

# Run pytest
docker run \
    --rm \
    --workdir=/app \
    --network=socorrosubmitter_default \
    --link=socorrosubmitter_rabbitmq_1 \
    --env-file=docker/lambda.env \
    socorrosubmitter_test pytest
