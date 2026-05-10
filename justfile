# list available recipes
default:
    @just --list

# lint and format
ruff:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# run tests
test:
    uv run pytest

# lint, format, then test
check: ruff test

# clean dist/ and build
build:
    rm -rf dist/
    uv build

# clean, build, and publish
publish:
    rm -rf dist/
    uv build
    uv publish

# open docs in the browser
docs:
    open docs/index.html || xdg-open docs/index.html
