#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Usage: docker-compose run lambda-build ./bin/run_build.sh

# Create the dir if it doesn't exist
test -d build/ || mkdir build/

# Install requirements
pip install --disable-pip-version-check --ignore-installed --no-cache-dir -r requirements.txt -t build/

# Copy submitter into package
cp src/submitter.py build/submitter.py
