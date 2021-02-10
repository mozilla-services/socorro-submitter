#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Run to build Python libraries into the build/ directory.
#
# Run this in the lambda-build container using "make build-libs".

# Failures should cause setup to fail
set -euxo pipefail

echo ">>> Building socorro-submitter..."

# Create the dir if it doesn't exist
test -d build/ || mkdir build/

# Install requirements and dependencies into build/ ignoring whatever was
# already in there
pip install \
    --disable-pip-version-check \
    --ignore-installed \
    --no-cache-dir \
    -r requirements.txt \
    --target build/

# Copy submitter into package
cp src/submitter.py build/submitter.py
