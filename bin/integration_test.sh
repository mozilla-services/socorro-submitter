#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# This runs an integration test by putting crash data into the source
# S3 bucket, invoking the submitter with an event, and then checking
# the dest S3 bucket to see if the bits are there.

set -e

HOSTUSER="$(id -u):$(id -g)"

SOURCEDIR="./fakedata_source/"
SOURCEBUCKET="s3://source_bucket/"

DESTDIR="./fakedata_dest/"
DESTBUCKET="s3://dest_bucket/"

# Start antenna and localstack-s3 containers
echo ">>> SETUP"

# Delete and recreate DESTDIR
rm -rf ${DESTDIR}
mkdir ${DESTDIR}

# Start localstack-s3 and make sure buckets are clean
# FIXME(willkg): need to wait until localstack-s3 is up
docker-compose up -d localstack-s3
# FIXME(willkg): check the bucket and delete it if it exists
docker-compose run -u "${HOSTUSER}" test bash -c "
    ./bin/aws_s3.sh rb --force ${SOURCEBUCKET} 2>&1 > /dev/null;
    ./bin/aws_s3.sh mb ${SOURCEBUCKET};
"
docker-compose run -u "${HOSTUSER}" test bash -c "
    ./bin/aws_s3.sh rb --force ${DESTBUCKET} 2>&1 > /dev/null;
    ./bin/aws_s3.sh mb ${DESTBUCKET}
"
# Start antenna
docker-compose up -d antenna

# Get a crash id from the fakecrashdata directory
# CRASHID=$(find fakecrashdata/ -type f | grep raw_crash | awk -F / '{print $6}')
CRASHID="11107bd0-2d1c-4865-af09-80bc00180313"
CRASHKEY="v2/raw_crash/${CRASHID:0:3}/20${CRASHID:30:6}/${CRASHID}"

# Copy source crash data into S3 source bucket
docker-compose run -u "${HOSTUSER}" test ./bin/aws_s3.sh sync ${SOURCEDIR} ${SOURCEBUCKET}

# Gemerate am event
echo ">>> GENERATE AN EVENT"
EVENT=$(./bin/generate_event.py --bucket source_bucket --key ${CRASHKEY})

# Loop until one of the invokes accepts the event and submits it to the
# destination collector
echo ">>> INVOKE UNTIL ACCEPTED"
IS_ACCEPT=
while [ -z "${ISACCEPT}" ]
do
    echo "Run invoke..."
    OUTPUT=$(echo "${EVENT}" | ./bin/run_invoke.sh 2>&1) || true
    ISACCEPT=$(echo "${OUTPUT}" | grep "socorro.submitter.accept") || true
    echo "${OUTPUT}"
done
echo ">>> Accepted!"

echo ">>> CHECK DEST ${DESTDIR} ${DESTBUCKET}"

# Copy S3 dest bucket into dest directory
docker-compose run -u "${HOSTUSER}" test ./bin/aws_s3.sh sync ${DESTBUCKET} ${DESTDIR}

# Check the data in the S3 dest bucket
FILES=$(cd ${SOURCEDIR} && find . -type f)
for FN in $FILES
do
    echo "Verifying ${SOURCEDIR}${FN} ${DESTDIR}${FN}..."
    ./bin/diff_files.py ${SOURCEDIR}${FN} ${DESTDIR}${FN}
done

echo ">>> SUCCESS: Integration test passed!"
