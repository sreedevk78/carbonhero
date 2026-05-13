import sys
import os

# Add the project root directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from run import app

# Vercel needs 'app' to be exposed at the module level
# Since we imported 'app' from run.py, it is already exposed.
