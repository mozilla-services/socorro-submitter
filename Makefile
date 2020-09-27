# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

DC := $(shell which docker-compose)
HOSTUSER := $(shell id -u):$(shell id -g)

.DEFAULT_GOAL := help
.PHONY: help
help:
	@echo "Usage: make RULE"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' Makefile \
	    | grep -v grep \
	    | sed -n 's/^\(.*\): \(.*\)##\(.*\)/\1\3/p' \
	    | column -t  -s '|'

.container-test:
	make build-containers

.PHONY: build-containers
build-containers:
	${DC} build test
	touch .container-test

.PHONY: build-libs
build-libs:
	${DC} run -u "${HOSTUSER}" lambda-build bash -c "cd /tmp && /tmp/bin/run_build.sh"

.PHONY: build
build: .container-test build-libs  ## | Build Docker images.

.PHONY: clean
clean:  ## | Remove build, test, and other artifacts.
	${DC} rm --stop --force -v
	-rm -rf build
	-rm .container-*
	-rm -rf fakedata_dest

.PHONY: lint
lint: .container-test  ## | Lint code.
	${DC} run test bin/run_lint.sh

.PHONY: lintfix
lintfix: .container-test  ## | Reformat code.
	${DC} run -u "${HOSTUSER}" test bin/run_lint.sh --fix

.PHONY: test
test: build  ## | Run tests.
	${DC} run test pytest -vv

.PHONY: testshell
testshell: build  ## | Open shell in test container.
	${DC} run test bash

.PHONY: runtimelist
runtimelist: build  ## | List python packages in lambda runtime image
	${DC} run --rm lambda-build bash -c "/tmp/bin/list_runtime_reqs.sh > /tmp/requirements-runtime.txt"
