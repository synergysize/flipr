# FlipR Backend Fix

This directory contains a fixed version of the FlipR backend to address the PostgreSQL connection errors:

```
psycopg2.OperationalError: invalid integer value "None" for connection option "port"
```

```
could not translate host name "None" to address: Name or service not known
```

and

```
Invalid DATABASE_URL format: DATABASE_URL=postgresql://postgres:zP8@m$Kd2L#qF*v7XrT9nH^Ew3Js!6B
@db.utalravvcgiehxojrgba.supabase.co:5432/postgres
```

## What was fixed

1. **Handling Newlines in URLs**: Fixed issue with newlines in DATABASE_URL (common copy-paste problem)
   ```python
   # Fix newlines in the URL (common copy-paste issue)
   DB_URL = DB_URL.replace("\n", "").replace("\r", "")
   ```

2. **Handling Prefixed Variables**: Fixed issue when the variable name is included in the value
   ```python
   # Remove var name if someone included it (DATABASE_URL=)
   if DB_URL.startswith("DATABASE_URL="):
       DB_URL = DB_URL.split("=", 1)[1]
   ```

3. **Default Connection Values**: Added default values for missing connection parameters
   ```python
   username = result.username or 'postgres'  # Default username
   hostname = result.hostname or 'localhost'  # Default to localhost if hostname is None
   port = result.port or 5432  # Use default PostgreSQL port if none specified
   ```

4. **Input Validation**: Added validation of the DATABASE_URL format
   ```python
   if not (result.scheme in ['postgresql', 'postgres'] and result.username and result.path):
       logging.warning(f"Invalid DATABASE_URL format: {DB_URL}")
       logging.warning("URL should be in format: postgres://username:password@hostname:port/database")
       DB_URL = ""
   ```

5. **Better Error Handling**: Improved error handling for database connections with better logging
   ```python
   logging.info(f"DATABASE_URL is {'set' if DB_URL else 'not set'}, using {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
   ```

6. **Automatic Fallback**: Added fallback mechanism to automatically switch to SQLite if PostgreSQL connection fails
   ```python
   try:
       # PostgreSQL initialization code...
   except Exception as e:
       logging.error(f"Failed to initialize PostgreSQL database: {str(e)}")
       logging.info("Falling back to SQLite database")
       globals()['USE_POSTGRES'] = False
       # Initialize SQLite instead...
   ```

7. **Environment Variable Loading**: Added dotenv support to load environment variables from a .env file
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

8. **Port Configuration**: Changed the default port to avoid conflicts
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