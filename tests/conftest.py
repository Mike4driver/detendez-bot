"""Pytest configuration and fixtures"""
import sys
import os
from pathlib import Path

# Add the project root to Python path so imports work
# This must happen before any test imports
project_root = Path(__file__).parent.parent
project_root_str = str(project_root.resolve())

# Add to sys.path if not already there
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Also set PYTHONPATH environment variable as a fallback
if 'PYTHONPATH' not in os.environ:
    os.environ['PYTHONPATH'] = project_root_str
elif project_root_str not in os.environ['PYTHONPATH']:
    os.environ['PYTHONPATH'] = project_root_str + os.pathsep + os.environ['PYTHONPATH']


def pytest_configure(config):
    """Pytest hook that runs before test collection"""
    # Ensure project root is in path (redundant but safe)
    project_root = Path(__file__).parent.parent
    project_root_str = str(project_root.resolve())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def pytest_collection_modifyitems(config, items):
    """Hook that runs after collection but can verify path setup"""
    # Verify path is set correctly
    project_root = Path(__file__).parent.parent
    project_root_str = str(project_root.resolve())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

