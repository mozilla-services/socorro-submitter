DC := $(shell which docker-compose)
HOSTUSER := $(shell id -u):$(shell id -g)

help:
	@echo "noop"

.container-test: 
	@echo "noop"

build-containers: .container-test

.PHONY: default build-containers

.DEFAULT_GOAL := help
