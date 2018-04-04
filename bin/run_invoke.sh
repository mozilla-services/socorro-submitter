#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Invokes the submitter lambda function in a python3.6 lambda runtime
# environment. Pass an event in via stdin.
#
# This turns around and uses lambci/lambda:python3.6, so any of those
# args will work, too.
#
# https://github.com/lambci/docker-lambda#example
#
# Usage: EVENT | ./bin/run_invoke.sh

# Note: Need to set DOCKER_LAMBDA_USE_STDIN to pipe events from stdin
docker-compose run \
               --rm \
               -v "$PWD/build":/var/task \
               --service-ports \
               -e DOCKER_LAMBDA_USE_STDIN=1 \
               lambda-run submitter.handler $@
