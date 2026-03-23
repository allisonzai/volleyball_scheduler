import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

# PythonAnywhere needs an event loop present before the app loads
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from a2wsgi import ASGIMiddleware
from app.main import app

application = ASGIMiddleware(app)
