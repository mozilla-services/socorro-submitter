#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Generates needed files so you can use aws cli with s3 subcommand against
# localstack running locally.
#
# Usage ./bin/aws_s3.sh [S3-CMDS]

set -euo pipefail

# Create required configuration files for aws
if [[ ! -d /tmp/.aws ]]
then
    mkdir /tmp/.aws
fi
if [[ ! -f /tmp/.aws/config ]]
then
    cat > /tmp/.aws/config <<EOF
[default]
EOF
fi
if [[ ! -f /tmp/.aws/credentials ]]
then
    cat > /tmp/.aws/credentials <<EOF
[default]
aws_access_key_id = ${SUBMITTER_S3_ACCESS_KEY}
aws_secret_access_key = ${SUBMITTER_S3_SECRET_ACCESS_KEY}
EOF
fi

HOME=/tmp aws --endpoint-url=${SUBMITTER_S3_ENDPOINT_URL} s3 $@
