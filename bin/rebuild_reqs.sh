#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Rebuilds the requirements*.txt files.

# Usage: ./bin/rebuild_reqs.sh

# This should be run in the test container.

set -euo pipefail

echo ">>> versions...."
pip --version
pip-compile --version

# Recompile requirements-dev.txt
echo ">>> recompile requirements-dev.txt...."
pip-compile --cache-dir=/tmp --generate-hashes --strip-extras --output-file /app/requirements-dev.txt /app/requirements-dev.in

# Recompile requirements.txt
echo ">>> recompile requirements.txt...."
pip-compile --cache-dir=/tmp --generate-hashes --strip-extras --output-file /app/requirements.txt /app/requirements.in
