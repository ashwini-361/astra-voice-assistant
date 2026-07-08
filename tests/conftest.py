"""Pytest configuration to enable module imports from parent directory."""
import sys
from pathlib import Path

import pytest

# Add the parent directory (ai-assistant/) to sys.path so pytest can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def anyio_backend():
    """Pin @pytest.mark.anyio tests to asyncio only.

    Without this override, anyio's default fixture parametrizes over
    every backend it knows about (asyncio + trio) -- trio isn't a
    project dependency, so those variants fail with
    ModuleNotFoundError rather than being skipped.
    """
    return "asyncio"
