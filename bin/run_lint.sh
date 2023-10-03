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

BLACKARGS=("--line-length=88" "--target-version=py36" bin src tests)
PYTHON_VERSION=$(python --version)

if [[ "${1:-}" == "--fix" ]]; then
    echo ">>> black fix"
    black "${BLACKARGS[@]}"

else
    cd /app

    echo ">>> flake8 (${PYTHON_VERSION})"
    flake8

    echo ">>> black (${PYTHON_VERSION})"
    black --check "${BLACKARGS[@]}"

    echo ">>> license check (${PYTHON_VERSION})"
    python bin/license-check.py bin
    python bin/license-check.py src
fi
