"""Copy into the PythonAnywhere Web tab's WSGI configuration file."""
import os
import sys
import time
from pathlib import Path

# Upload app code to ~/travelicious and private business data to ~/travelicious-data.
project = Path.home() / 'travelicious'
os.environ['INVENTORY_DATA'] = str(Path.home() / 'travelicious-data')
os.environ['HTTPS'] = '1'
os.environ['TZ'] = 'Asia/Kolkata'
time.tzset()
sys.path.insert(0, str(project))
from production import app as application
