DC := $(shell which docker-compose)
HOSTUSER := $(shell id -u):$(shell id -g)

.PHONY: help
help: default

.PHONY: default
default:
	@echo "Please do \"make <TARGET>\" where TARGET is one of:"
	@echo "  build        - install Python libs and build Docker containers"
	@echo "  test         - run tests"
	@echo "  testshell    - open a shell in the test container"
	@echo "  clean        - remove build files"

.container-test: docker/test/Dockerfile requirements-dev.txt
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

.PHONY: test-flake8
test-flake8: .container-test
	${DC} run test flake8 src/

.PHONY: test-pytest
test-pytest: .container-test
	${DC} run test py.test

.PHONY: test
test: test-flake8 test-pytest

.PHONY: testshell
testshell: .container-test
	${DC} run test bash
