#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: docker/run_lint.sh [--fix]
#
# Runs linting and code fixing.
#
# This should be called from inside a container.

set -euo pipefail

PYTHON_VERSION=$(python --version)

cd /app

echo ">>> ruff (${PYTHON_VERSION})"
ruff format --check bin src tests
ruff check bin src tests

echo ">>> license check (${PYTHON_VERSION})"
python bin/license-check.py bin
python bin/license-check.py src
