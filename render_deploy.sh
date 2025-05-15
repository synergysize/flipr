#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Export production environment
export PRODUCTION=true
export DISABLE_SQLITE_FALLBACK=true

# Initialize the database
python -c "from fixed_backend import init_db; init_db()"

# Start the application
exec gunicorn --worker-class eventlet -w 1 fixed_backend:app