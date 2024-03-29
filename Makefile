# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Include my.env and export it so variables set in there are available
# in the Makefile.
include my.env
export

# Set these in the environment to override them. This is helpful for
# development if you have file ownership problems because the user
# in the container doesn't match the user on your host.
APP_UID ?= 10001
APP_GID ?= 10001

HOSTUSER := $(shell id -u):$(shell id -g)

DOCKER := $(shell which docker)
DC=${DOCKER} compose

.DEFAULT_GOAL := help
.PHONY: help
help:
	@echo "Usage: make RULE"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' Makefile \
	    | grep -v grep \
	    | sed -n 's/^\(.*\): \(.*\)##\(.*\)/\1\3/p' \
	    | column -t  -s '|'

my.env:
	@if [ ! -f my.env ]; \
		then \
		echo "Copying my.env.dist to my.env..."; \
		cp docker/my.env.dist my.env; \
	fi

.container-test:
	make build-containers

.PHONY: build-containers
build-containers: my.env
	${DC} build --build-arg userid=${APP_UID} --build-arg groupid=${APP_GID} --progress plain test
	${DC} build --progress plain localstack
	touch .container-test

.PHONY: build-libs
build-libs: my.env
	${DC} run -u "${HOSTUSER}" lambda-build bash -c "cd /tmp && /tmp/bin/run_build.sh"

.PHONY: build
build: build-containers build-libs  ## | Build Docker images.

.PHONY: clean
clean:  ## | Remove build, test, and other artifacts.
	${DC} rm --stop --force -v
	-rm -rf build
	-rm .container-*
	-rm -rf fakedata_dest

.PHONY: format
format: .container-test  ## | Format code.
	${DC} run -u "${HOSTUSER}" test ruff format

.PHONY: lint
lint: .container-test  ## | Lint code.
	${DC} run test bin/run_lint.sh

.PHONY: test
test: build  ## | Run tests.
	${DC} run test pytest -vv

.PHONY: testshell
testshell: build  ## | Open shell in test container.
	${DC} run test bash

.PHONY: rebuildreqs
rebuildreqs: .container-test  ## | Update requirements*.txt files.
	${DC} run --rm -u "${HOSTUSER}" lambda-build bash -c "/tmp/bin/list_runtime_reqs.sh > /tmp/requirements-runtime.txt"
	${DC} run --rm --no-deps -u "${HOSTUSER}" test /app/bin/rebuild_reqs.sh
