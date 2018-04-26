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
rm -rf "${DESTDIR}"
mkdir "${DESTDIR}"

# Start localstack-s3 and make sure buckets are clean
docker-compose up -d localstack-s3
# NOTE(willkg): This is localhost:5000 from the host and localstack-s3:5000
# from inside the containers.
./bin/wait.sh localhost 5000

# FIXME(willkg): check the bucket and delete it if it exists
docker-compose run -u "${HOSTUSER}" test bash -c "
    ./bin/aws_s3.sh rb --force ${SOURCEBUCKET} >/dev/null 2>&1;
    ./bin/aws_s3.sh mb ${SOURCEBUCKET};
"
docker-compose run -u "${HOSTUSER}" test bash -c "
    ./bin/aws_s3.sh rb --force ${DESTBUCKET} >/dev/null 2>&1;
    ./bin/aws_s3.sh mb ${DESTBUCKET}
"
# Start antenna
docker-compose up -d antenna
# NOTE(willkg): This is localhost:8888 from the host and antenna:8888
# from inside the containers.
./bin/wait.sh localhost 8888

# Get a crash id from the fakecrashdata directory
# CRASHID=$(find fakecrashdata/ -type f | grep processed_crash | awk -F / '{print $6}')
CRASHID="11107bd0-2d1c-4865-af09-80bc00180313"
CRASHKEY="v1/processed_crash/${CRASHID}"

# Copy source crash data into S3 source bucket
docker-compose run -u "${HOSTUSER}" test ./bin/aws_s3.sh sync "${SOURCEDIR}" "${SOURCEBUCKET}"

# Generate am event
echo ">>> GENERATE AN EVENT"
EVENT=$(./bin/generate_event.py --bucket source_bucket --key "${CRASHKEY}")

# Run invoke with THROTTLE=0 (submit nothing) and make sure it prints
# "throttled"
OUTPUT=$(echo "${EVENT}" | THROTTLE=0 ./bin/run_invoke.sh 2>&1) || true
echo "${OUTPUT}"
ISTHROTTLE=$(echo "${OUTPUT}" | grep "socorro.submitter.throttled") || true
if [ -z "${ISTHROTTLE}" ]
then
    echo ">>> FAILED: THROTTLE=0, but \"throttled\" not printed out."
    exit 1
fi

# Make sure nothing is in the dest bucket and thus nothing got submitted
CONTENTS=$(docker-compose run --rm test ./bin/aws_s3.sh ls "${DESTBUCKET}")
if [ "${CONTENTS}" != "" ]
then
    echo ">>> FAILED: THROTTLE=0, but something is in the dest bucket."
    exit 1
fi
echo ">>> SUCCESS: THROTTLE=0 case submitted nothing!"

# Run invoke with THROTTLE=100 (submit everything) and make sure it prints
# "accept"
OUTPUT=$(echo "${EVENT}" | THROTTLE=100 ./bin/run_invoke.sh 2>&1)
echo "${OUTPUT}"
ISACCEPT=$(echo "${OUTPUT}" | grep "socorro.submitter.accept") || true
if [ -z "${ISTHROTTLE}" ]
then
    echo ">>> FAILED: THROTTLE=100, but \"accept\" not printed out."
    exit 1
fi

# Copy S3 dest bucket into dest directory
docker-compose run -u "${HOSTUSER}" --rm test ./bin/aws_s3.sh sync "${DESTBUCKET}" "${DESTDIR}"

# Make sure the crash is in the dest bucket and has the correct contents
FILES=$(cd ${SOURCEDIR} && find . -type f)
for FN in $FILES
do
    echo "Verifying ${SOURCEDIR}${FN} ${DESTDIR}${FN}..."
    ./bin/diff_files.py "${SOURCEDIR}${FN}" "${DESTDIR}${FN}"
done
echo ">>> SUCCESS: THROTTLE=100 case submitted data correctly!"

echo ">>> SUCCESS: Integration test passed!"
