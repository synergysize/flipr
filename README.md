# FlipR Backend Fix

This directory contains a fixed version of the FlipR backend to address the PostgreSQL connection error:

```
psycopg2.OperationalError: invalid integer value "None" for connection option "port"
```

## What was fixed

1. **Port Default Value**: Added default port (5432) for PostgreSQL when no port is specified in the connection URL
   ```python
   port = result.port or 5432  # Use default PostgreSQL port if none specified
   ```

2. **Better Error Handling**: Improved error handling for database connections with better logging
   ```python
   logging.info(f"DATABASE_URL is {'set' if DB_URL else 'not set'}, using {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
   ```

3. **Automatic Fallback**: Added fallback mechanism to automatically switch to SQLite if PostgreSQL connection fails
   ```python
   try:
       # PostgreSQL initialization code...
   except Exception as e:
       logging.error(f"Failed to initialize PostgreSQL database: {str(e)}")
       logging.info("Falling back to SQLite database")
       globals()['USE_POSTGRES'] = False
       # Initialize SQLite instead...
   ```

4. **Environment Variable Loading**: Added dotenv support to load environment variables from a .env file
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

5. **Port Configuration**: Changed the default port to avoid conflicts
   ```python
   port = int(os.environ.get("PORT", 5005))
   ```

## How to use

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure database (optional):
   - Edit the `.env` file to configure PostgreSQL connection
   - By default, it will use SQLite

3. Run the application:
   ```bash
   python fixed_backend.py
   ```

The application will run on port 5005 by default (http://localhost:5005).