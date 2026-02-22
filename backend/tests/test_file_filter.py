import pytest

from services.file_filter import should_include, MAX_FILE_BYTES


# --- Files that SHOULD be included ---


@pytest.mark.parametrize(
    "path,size",
    [
        ("README.md", 500),
        ("src/main.py", 1000),
        ("frontend/src/app/page.tsx", 800),
        ("components/Button.tsx", 200),
        ("config.yaml", 300),
        ("pyproject.toml", 400),
        ("Makefile", 600),
        ("Dockerfile", 700),
        ("schema.graphql", 900),
        ("migrations/001_init.sql", 500),
    ],
)
def test_included_files(path, size):
    assert should_include(path, size) is True


# --- Files that SHOULD be excluded ---


@pytest.mark.parametrize(
    "path,size,reason",
    [
        ("node_modules/lodash/index.js", 500, "node_modules dir"),
        (".git/config", 100, ".git dir"),
        ("dist/bundle.js", 500, "dist dir"),
        ("build/output.js", 500, "build dir"),
        (".next/server/app.js", 500, ".next dir"),
        ("venv/lib/python3.11/site.py", 200, "venv dir"),
        (".venv/lib/python3.11/site.py", 200, ".venv dir"),
        ("image.png", 5000, "binary extension"),
        ("photo.jpg", 5000, "binary extension"),
        ("archive.zip", 5000, "binary extension"),
        ("binary.exe", 5000, "binary extension"),
        ("font.woff2", 5000, "binary extension"),
        ("big_file.py", MAX_FILE_BYTES + 1, "exceeds size limit"),
    ],
)
def test_excluded_files(path, size, reason):
    assert (
        should_include(path, size) is False
    ), f"Expected {path} to be excluded ({reason})"


def test_binary_guess_excludes():
    assert should_include("somefile.py", 100, is_binary_guess=True) is False


def test_size_exactly_at_limit_is_included():
    assert should_include("ok.py", MAX_FILE_BYTES) is True


def test_size_one_over_limit_is_excluded():
    assert should_include("big.py", MAX_FILE_BYTES + 1) is False
