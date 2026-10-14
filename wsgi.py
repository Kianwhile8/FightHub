"""WSGI entry point for production (Gunicorn, uWSGI, etc.).

Usage:
    gunicorn wsgi:app
    gunicorn wsgi:app --workers 4 --bind 0.0.0.0:5000

Development:
    python wsgi.py
"""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5000)
