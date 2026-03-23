# PythonAnywhere WSGI entry point.
# Wraps the FastAPI (ASGI) app as a WSGI app using a2wsgi.
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from a2wsgi import ASGIMiddleware
from app.main import app

application = ASGIMiddleware(app)
