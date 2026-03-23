import sys
import os

# Must set working directory BEFORE importing the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load .env explicitly before app config is read
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from a2wsgi import ASGIMiddleware
from app.main import app

application = ASGIMiddleware(app)
