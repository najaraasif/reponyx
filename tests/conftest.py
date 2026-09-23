import tempfile
import os

# Override the default temp directory to avoid permission issues on Windows
# The default pytest-of-<user> directory can get locked
_temp_dir = os.path.join(tempfile.gettempdir(), "reponyx-pytest")
os.makedirs(_temp_dir, exist_ok=True)
