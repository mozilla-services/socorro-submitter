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
	${DC} build test
	touch .container-test

.PHONY: build-containers
build-containers: .container-test

.PHONY: build-libs
build-libs:
	${DC} run -u "${HOSTUSER}" lambda-build bash -c "cd /tmp && /tmp/bin/run_build.sh"

.PHONY: build
build: build-containers build-libs  ## | Build Docker images.

.PHONY: clean
clean:  ## | Remove build, test, and other artifacts.
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
test: .container-test  ## | Run tests.
	${DC} run test py.test

.PHONY: testshell  ## | Open shell in test container.
testshell: .container-test
	${DC} run test bash
