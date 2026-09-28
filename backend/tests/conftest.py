"""Use ordinary workspace directories on Windows (pytest's 0700 ACL is unreliable)."""
from pathlib import Path
from uuid import uuid4
import pytest

@pytest.fixture
def tmp_path():
    path = Path(__file__).parents[2] / ".test-artifacts" / uuid4().hex
    path.mkdir(parents=True)
    return path
