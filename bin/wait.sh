#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

HOST="$1"
PORT="$2"

TIMEOUT=10

count=0

echo "Connecting to ${HOST}:${PORT}..."
while :
do
    if [ ${count} -ge ${TIMEOUT} ];
    then
        echo "Timeout after ${TIMEOUT} seconds."
        exit 1
    fi

    nc -z ${HOST} ${PORT}
    if [ $? -eq 0 ]
    then
        echo "Success!"
        break
    fi
    echo "Waiting... (${count}/${TIMEOUT})"
    sleep 1

    count=$((count+1))
done
