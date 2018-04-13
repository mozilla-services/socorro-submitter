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

# FIXME(willkg): Implement this
