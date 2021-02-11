#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# This runs an integration test by putting crash data into the source
# S3 bucket, invoking the submitter with an event, and then checking
# the dest S3 bucket to see if the bits are there.

set -euo pipefail

newtest() {
    echo ""
    echo "========================================================================"
    echo ">>> $1"
    echo "========================================================================"
    echo ""
}

reportsuccess() {
    echo ""
    echo -e "\033[0;32m>>> TEST SUCCESS $1\033[0m"
    echo ""
}

reportfail() {
    echo ""
    echo -e "\033[1;31m>>> TEST FAILED $1\033[0m"
    echo ""
}

trap "reportfail ." 0

HOSTUSER="$(id -u):$(id -g)"

SOURCEDIR="./fakedata_source/"
# NOTE(willkg): this matches docker/lambda.env SUBMITTER_S3_BUCKET
SOURCEBUCKET="s3://source-bucket/"

DESTDIR="./fakedata_dest/"
# NOTE(willkg): this matches docker/antenna.env CRASHSTORAGE_BUCKET_NAME
DESTBUCKET="s3://dest-bucket/"

# Start antenna and localstack-s3 containers
echo ">>> SETUP"

# Delete and recreate DESTDIR
rm -rf "${DESTDIR}"
mkdir "${DESTDIR}"

# Start localstack and make sure buckets are clean
docker-compose up -d localstack
# NOTE(willkg): This is localhost:4566 from the host and localstack:4566
# from inside the containers.
./bin/wait.sh localhost 4566

# Set up integration test
docker-compose run -u "${HOSTUSER}" test ./bin/setup_integration_test.sh

# Start antenna
docker-compose up -d antenna
# NOTE(willkg): This is localhost:8888 from the host and antenna:8888
# from inside the containers.
./bin/wait.sh localhost 8888

# Remove anything in the bucket that Antenna generated at startup so we have an
# empty bucket to work with.
docker-compose run -u "${HOSTUSER}" test ./bin/aws_s3.sh rm "${DESTBUCKET}" --recursive

# Get a crash id from the fakecrashdata directory
# CRASHID=$(find fakecrashdata/ -type f | grep raw_crash | awk -F / '{print $6}')
CRASHID="11107bd0-2d1c-4865-af09-80bc00180313"
CRASHKEY="v2/raw_crash/111/20180313/${CRASHID}"

# Copy source crash data into S3 source bucket
docker-compose run -u "${HOSTUSER}" test ./bin/aws_s3.sh sync "${SOURCEDIR}" "${SOURCEBUCKET}"

# Generate am event
echo ">>> GENERATE AN EVENT"
EVENT=$(./bin/generate_event.py --bucket source_bucket --key "${CRASHKEY}")

# ==============================================================================
newtest "THROTTLE=0 (submit nothing) and make sure it prints 'throttled'"

OUTPUT=$(echo "${EVENT}" | THROTTLE=0 ./bin/run_invoke.sh 2>&1) || true
echo "${OUTPUT}"
ISTHROTTLE=$(echo "${OUTPUT}" | grep "socorro.submitter.throttled") || true
if [ -z "${ISTHROTTLE}" ]
then
    reportfail "THROTTLE=0, but \"throttled\" not printed out."
    exit 1
fi

# Make sure nothing is in the dest bucket and thus nothing got submitted
CONTENTS=$(docker-compose run --rm test ./bin/aws_s3.sh ls "${DESTBUCKET}")
if [ "${CONTENTS}" != "" ]
then
    echo "Contents: ${CONTENTS}"
    reportfail "THROTTLE=0, but something is in the dest bucket."
    exit 1
fi
reportsuccess "THROTTLE=0 case submitted nothing!"

# ==============================================================================
newtest "THROTTLE=100 (submit everything) and make sure it prints 'accept'"

OUTPUT=$(echo "${EVENT}" | THROTTLE=100 ./bin/run_invoke.sh 2>&1)
echo "${OUTPUT}"
ISACCEPT=$(echo "${OUTPUT}" | grep "socorro.submitter.accept") || true
if [ -z "${ISTHROTTLE}" ]
then
    reportfail "THROTTLE=100, but \"accept\" not printed out."
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
reportsuccess "THROTTLE=100 case submitted data correctly!"

# If we got here, then the test succeeded, so nix the trap
trap - 0

echo -e "\033[0;32mSuccess!\033[0m"
