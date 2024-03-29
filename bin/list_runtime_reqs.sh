#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Lists runtime requirements to stdout.

# Usage: ./bin/list_runtime_reqs.sh

# This should be run in the lambda-build container.

set -euo pipefail

echo "# Auto-generated by bin/list_runtime_reqs.sh at $(date)"
# Lists what's installed ...
# minus the header lines
# converting the two columns into A==B
# ignoring pip== lines
# ignoring rapid-client== lines
pip list | \
    tail -n +3 | \
    sed -r 's/( )+/==/g' | \
    grep -v "pip==" | \
    grep -v "rapid-client=="
