# Auto-generated Makefile
.PHONY: lint format type-check

lint:
	uvx ruff check

format:
	uvx ruff format

type-check:
	uvx ty check
