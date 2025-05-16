# Auto-generated Makefile
.PHONY: lint format type-check test

lint:
	uvx ruff check

format:
	uvx ruff format

type-check:
	uvx ty check

test:
	uv run pytest
