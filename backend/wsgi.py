import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from app.main import app  # init_db() runs here at import time

# Lazy wrapper: ASGIMiddleware is created on the first request inside the
# worker process (after uWSGI fork), so its event-loop thread is alive.
_asgi = None

def application(environ, start_response):
    global _asgi
    if _asgi is None:
        from a2wsgi import ASGIMiddleware
        _asgi = ASGIMiddleware(app)
    return _asgi(environ, start_response)
