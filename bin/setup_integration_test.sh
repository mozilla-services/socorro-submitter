#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Sets up S3 buckets for integration test.

if [ -z "${SUBMITTER_S3_BUCKET}" ]; then
    echo "SUBMITTER_S3_BUCKET is not set."
    exit 1;
fi

if [ -z "${CRASHSTORAGE_BUCKET_NAME}" ]; then
    echo "CRASHSTORAGE_BUCKET_NAME is not set."
    exit 1;
fi

./bin/aws_s3.sh rb --force s3://${SUBMITTER_S3_BUCKET}/ 2>&1 > /dev/null
./bin/aws_s3.sh mb s3://${SUBMITTER_S3_BUCKET}/

./bin/aws_s3.sh rb --force s3://${CRASHSTORAGE_BUCKET_NAME}/ 2>&1 > /dev/null
./bin/aws_s3.sh mb s3://${CRASHSTORAGE_BUCKET_NAME}/
