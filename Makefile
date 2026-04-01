SHELL := /bin/bash

PYTHON ?= python3
VENV ?= .venv
VENV_BIN := $(VENV)/bin
PYTHON_BIN := $(VENV_BIN)/python
PIP_BIN := $(VENV_BIN)/pip
PYSIDE_DEPLOY := $(VENV_BIN)/pyside6-deploy
SPEC_FILE := pysidedeploy.spec

.DEFAULT_GOAL := help

.PHONY: help venv install run test build-linux build-linux-onefile build-linux-standalone clean check-linux-host

help:
	@echo "Available targets:"
	@echo "  make install                 Create $(VENV) and ensure PySide6 is available"
	@echo "  make run                     Launch the GUI application"
	@echo "  make test                    Run unit tests"
	@echo "  make build-linux             Build a onefile Linux executable with pyside6-deploy"
	@echo "  make build-linux-standalone  Build a standalone Linux bundle with pyside6-deploy"
	@echo "  make clean                   Remove virtualenv caches and build artifacts"

$(PYTHON_BIN):
	$(PYTHON) -m venv $(VENV)

venv: $(PYTHON_BIN)

install: venv
	@if ! $(PYTHON_BIN) -c "import PySide6" >/dev/null 2>&1; then \
		$(PIP_BIN) install PySide6; \
	fi

run: install
	$(PYTHON_BIN) app.py

test: install
	$(PYTHON_BIN) -m unittest tests.test_core

check-linux-host:
	@if [ "$$(uname -s)" != "Linux" ]; then \
		echo "Linux build targets must be run on a Linux host."; \
		echo "Current host: $$(uname -s)"; \
		exit 1; \
	fi

build-linux: build-linux-onefile

build-linux-onefile: install check-linux-host
	$(PYSIDE_DEPLOY) -c $(SPEC_FILE) --mode onefile --force

build-linux-standalone: install check-linux-host
	$(PYSIDE_DEPLOY) -c $(SPEC_FILE) --mode standalone --force

clean:
	rm -rf $(VENV) build deployment dist __pycache__ .pytest_cache .mypy_cache
