
import sys
import os

# Add the project root directory to the Python path.
# This allows the test runner to find and import modules from the 'src' directory,
# resolving ModuleNotFoundError issues during test collection and execution.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
