# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

DC := $(shell which docker-compose)
HOSTUSER := $(shell id -u):$(shell id -g)

.PHONY: help
help: default

.PHONY: default
default:
	@echo "Please do \"make <TARGET>\" where TARGET is one of:"
	@echo "  build        - install Python libs and build Docker containers"
	@echo "  lint         - lint code"
	@echo "  lintfix      - reformat code"
	@echo "  test         - run tests"
	@echo "  testshell    - open a shell in the test container"
	@echo "  clean        - remove build files"

.container-test:
	${DC} build test
	touch .container-test

.PHONY: build-containers
build-containers: .container-test

.PHONY: build-libs
build-libs:
	${DC} run -u "${HOSTUSER}" lambda-build bash -c "cd /tmp && /tmp/bin/run_build.sh"

.PHONY: build
build: build-containers build-libs

.PHONY: clean
clean:
	-rm -rf build
	-rm .container-*
	-rm -rf fakedata_dest

.PHONY: lint
lint: .container-test
	${DC} run test bin/run_lint.sh

.PHONY: lintfix
lintfix: .container-test
	${DC} run -u "${HOSTUSER}" test bin/run_lint.sh --fix

.PHONY: test
test: .container-test
	${DC} run test py.test

.PHONY: testshell
testshell: .container-test
	${DC} run test bash
