from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

import json
import os
import time
import logging
import uuid
import psycopg2
import psycopg2.extras
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fixed_backend.log"),
        logging.StreamHandler()
    ]
)

app = Flask(__name__, static_folder='.')

# Allow specific origins for CORS - add your Vercel app URL here
ALLOWED_ORIGINS = [
    "https://flipr-app.vercel.app",  # Replace with your actual Vercel app URL
    "https://app.flipr.realty",      # Production domain
    "http://app.flipr.realty",       # Production domain (http version)
    "http://localhost:3000",         # For local development
    "http://localhost:5173",          # For local Vite development
    "https://flipr-5.onrender.com",
    "https://flipr-6.onrender.com",
    "*"                              # Allow all origins in development mode
]

CORS(app, origins=ALLOWED_ORIGINS)
# For Gunicorn compatibility, we'll set async_mode to 'eventlet'
socketio = SocketIO(app, cors_allowed_origins=ALLOWED_ORIGINS, async_mode='eventlet')

# Get from environment variable
# Use explicit Supabase pooler URL if environment doesn't specify one
DEFAULT_DB_URL = "postgresql://postgres.utalravvcgiehxojrgba:GX0JblzDEbyYxi6k@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
DB_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

# Log which database URL we're using
if DB_URL == DEFAULT_DB_URL:
    logging.info("Using default Supabase pooler connection URL")
else:
    logging.info("Using DATABASE_URL from environment")

# Check for common mistakes in DATABASE_URL
if DB_URL:
    # Remove var name if someone included it (DATABASE_URL=)
    if DB_URL.startswith("DATABASE_URL="):
        DB_URL = DB_URL.split("=", 1)[1]
        logging.info(f"Removed 'DATABASE_URL=' prefix from connection string")

    # Fix newlines in the URL (common copy-paste issue)
    DB_URL = DB_URL.replace("\n", "").replace("\r", "")
    
    # Validate DATABASE_URL format
    try:
        # Special handling for URLs with special characters
        # We don't want to be too strict here - if the URL has the basic format, we'll accept it
        # and rely on the more detailed validation in get_db_connection
        
        # Just check that it starts with postgres:// or postgresql:// and has at least one /@
        if (DB_URL.startswith('postgres://') or DB_URL.startswith('postgresql://')) and '@' in DB_URL:
            logging.info(f"Database URL format seems valid, proceeding with connection attempt")
        else:
            logging.warning(f"Invalid DATABASE_URL format: {DB_URL}")
            logging.warning("URL should be in format: postgres://username:password@hostname:port/database")
            DB_URL = ""
    except Exception as e:
        logging.warning(f"Error parsing DATABASE_URL: {str(e)}")
        DB_URL = ""

# Check if SQLite fallback is disabled
DISABLE_SQLITE_FALLBACK = os.environ.get("DISABLE_SQLITE_FALLBACK", "").lower() in ["true", "1", "yes"]
# Default to production mode if not specified (safer approach for deployment)
IS_PRODUCTION = os.environ.get("PRODUCTION", "true").lower() in ["true", "1", "yes"]

# Always use PostgreSQL in production and with our default connection
USE_POSTGRES = True

# Log the mode we're running in
if IS_PRODUCTION:
    logging.info("Running in PRODUCTION mode")
else:
    logging.info("Running in DEVELOPMENT mode")

# Even in development mode, we'll use PostgreSQL with our default connection
logging.info(f"Database connection configured to use PostgreSQL")

# IPv4 patch to force IPv4 connections
import socket

# Save the original getaddrinfo function
orig_getaddrinfo = socket.getaddrinfo

# This function will filter out IPv6 results and only return IPv4
def force_ipv4(*args, **kwargs):
    # Force IPv4 by explicitly adding family=socket.AF_INET parameter
    kwargs['family'] = socket.AF_INET
    return orig_getaddrinfo(*args, **kwargs)

# Replace the original getaddrinfo with our IPv4-only version
socket.getaddrinfo = force_ipv4

# Also create a more restrictive version of psycopg2.connect
import psycopg2
orig_psycopg2_connect = psycopg2.connect

# Wrap psycopg2.connect to force IPv4
def ipv4_psycopg2_connect(dsn, **kwargs):
    if 'host=' in dsn:
        # For connection strings in the "host=X port=Y..." format
        params = {}
        for param in dsn.split():
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        if 'host' in params:
            # Get the IPv4 address for the hostname
            logging.info(f"Resolving hostname {params['host']} to IPv4 address")
            try:
                # Force IPv4 address resolution
                ipv4_addr = socket.gethostbyname(params['host'])
                logging.info(f"Resolved to IPv4 address: {ipv4_addr}")
                
                # Replace the hostname with the IPv4 address in the connection string
                dsn = dsn.replace(f"host={params['host']}", f"host={ipv4_addr}")
            except Exception as e:
                logging.warning(f"Failed to resolve hostname to IPv4: {str(e)}")
    
    elif '//' in dsn:
        # For URLs like postgresql://username:password@hostname:port/database
        try:
            result = urllib.parse.urlparse(dsn)
            if result.hostname:
                logging.info(f"Resolving hostname {result.hostname} to IPv4 address")
                # Force IPv4 address resolution
                ipv4_addr = socket.gethostbyname(result.hostname)
                logging.info(f"Resolved to IPv4 address: {ipv4_addr}")
                
                # Reconstruct the URL with the IPv4 address
                netloc = result.netloc.replace(result.hostname, ipv4_addr)
                new_url = urllib.parse.urlunparse((
                    result.scheme, netloc, result.path,
                    result.params, result.query, result.fragment
                ))
                dsn = new_url
        except Exception as e:
            logging.warning(f"Failed to modify URL to use IPv4: {str(e)}")
    
    # Call the original connect function with our potentially modified dsn
    return orig_psycopg2_connect(dsn, **kwargs)

# Replace psycopg2.connect with our IPv4-enforcing version
psycopg2.connect = ipv4_psycopg2_connect

# Log connection method being used
logging.info(f"DATABASE_URL is {'set' if DB_URL else 'not set'}, using {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
DB_FILE = "properties.db"

def get_db_connection():
    """Get database connection (either PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        try:
            # For complex URLs with special characters, try connecting directly with the URL
            # This is more reliable than parsing the URL ourselves
            try:
                # Try direct connection with the URL first
                logging.info("Attempting direct connection with the DATABASE_URL")
                conn = psycopg2.connect(DB_URL)
                return conn
            except Exception as direct_err:
                # If direct connection fails, try parsing the URL and connecting with components
                logging.warning(f"Direct connection failed: {str(direct_err)}")
                logging.info("Trying to parse URL components and connect manually")
                
                # Parse the DATABASE_URL to extract components
                result = urllib.parse.urlparse(DB_URL)
                
                # Extract components with defaults for missing values
                username = result.username or 'postgres'  # Default username
                password = result.password  # Password can be None
                database = result.path[1:] if result.path else None  # Remove the leading '/'
                hostname = result.hostname or 'localhost'  # Default to localhost if hostname is None
                port = result.port or 5432  # Use default PostgreSQL port if none specified
                
                # Validate essential components
                if not database:
                    raise ValueError("Database name is missing in DATABASE_URL")
                
                # Create a proper connection string for PostgreSQL with proper handling of None values
                conn_string = f"host={hostname} port={port} dbname={database} user={username}"
                if password:
                    conn_string += f" password={password}"
                conn_string += " sslmode=require"
                
                logging.info(f"Connecting with parameters - host: {hostname}, port: {port}, dbname: {database}, user: {username}")
                
                # Connect using the parsed parameters
                conn = psycopg2.connect(conn_string)
                return conn
        except Exception as e:
            logging.error(f"Error connecting to PostgreSQL: {str(e)}")
            raise
    else:
        # Fallback to SQLite
        import sqlite3
        return sqlite3.connect(DB_FILE)

def init_db():
    """Initialize database tables"""
    if USE_POSTGRES:
        try:
            # PostgreSQL initialization
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS properties (
                        id TEXT PRIMARY KEY,
                        address TEXT,
                        lat REAL,
                        lng REAL,
                        price REAL,
                        bedrooms INTEGER,
                        bathrooms REAL,
                        intensity REAL,
                        deal_rating TEXT,
                        ai_evaluation_reasoning TEXT,
                        property_data JSONB,
                        timestamp INTEGER
                    )
                    ''')
                    conn.commit()
            logging.info("PostgreSQL database initialized")
        except Exception as e:
            logging.error(f"Failed to initialize PostgreSQL database: {str(e)}")
            if IS_PRODUCTION or DISABLE_SQLITE_FALLBACK:
                # In production, do not fall back to SQLite
                raise
            else:
                # Only in development, fall back to SQLite
                logging.info("Falling back to SQLite database in development mode")
                # Set the global variable to switch to SQLite
                globals()['USE_POSTGRES'] = False
                # Initialize SQLite instead
                import sqlite3
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS properties (
                        id TEXT PRIMARY KEY,
                        address TEXT,
                        lat REAL,
                        lng REAL,
                        price REAL,
                        bedrooms INTEGER,
                        bathrooms REAL,
                        intensity REAL,
                        deal_rating TEXT,
                        ai_evaluation_reasoning TEXT,
                        property_data TEXT,
                        timestamp INTEGER
                    )
                    ''')
                    conn.commit()
                logging.info("SQLite database initialized (development fallback mode)")
    else:
        # SQLite initialization (for development)
        import sqlite3
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                address TEXT,
                lat REAL,
                lng REAL,
                price REAL,
                bedrooms INTEGER,
                bathrooms REAL,
                intensity REAL,
                deal_rating TEXT,
                ai_evaluation_reasoning TEXT,
                property_data TEXT,
                timestamp INTEGER
            )
            ''')
            conn.commit()
        logging.info("SQLite database initialized (development mode)")

# API routes
@app.route('/')
def serve_map():
    return send_from_directory('.', 'index.html')

@app.route('/update', methods=['POST'])
def update_property():
    try:
        property_data = request.json
        
        # Ensure standard coordinates format
        if 'latitude' in property_data and 'lat' not in property_data:
            property_data['lat'] = property_data['latitude']
        if 'longitude' in property_data and 'lng' not in property_data:
            property_data['lng'] = property_data['longitude']
        
        # Generate ID if not provided
        if 'id' not in property_data:
            property_data['id'] = str(uuid.uuid4())
        
        # Current timestamp if not provided
        if 'timestamp' not in property_data:
            property_data['timestamp'] = int(time.time())
        
        # Extract standard fields
        city = property_data.get('city')
        state = property_data.get('state')
        zip_code = property_data.get('zip')
        square_feet = property_data.get('square_feet')
        year_built = property_data.get('year_built')
        lot_size = property_data.get('lot_size')
        walk_score = property_data.get('walk_score')
        property_type = property_data.get('property_type')
        prop_id = property_data.get('id')
        address = property_data.get('address', '')
        lat = property_data.get('lat')
        lng = property_data.get('lng')
        price = property_data.get('price')
        bedrooms = property_data.get('bedrooms')
        bathrooms = property_data.get('bathrooms')
        intensity = property_data.get('intensity', 0.5)
        deal_rating = property_data.get('deal_rating')
        ai_reasoning = property_data.get('ai_evaluation_reasoning')
        
        # Extra fields go to property_data
        extra_fields = {}
        standard_fields = ['id', 'address', 'lat', 'lng', 'price', 'bedrooms', 'bathrooms', 'city', 'state', 'zip_code', 'square_feet', 'year_built', 'lot_size', 'walk_score', 'property_type', 
                          'bathrooms', 'intensity', 'deal_rating', 
                          'ai_evaluation_reasoning', 'timestamp']
        
        for key, value in property_data.items():
            if key not in standard_fields:
                extra_fields[key] = value
        
        # Save to database
        conn = get_db_connection()
        try:
            if USE_POSTGRES:
                with conn.cursor() as cursor:
                    cursor.execute('''
                    INSERT INTO properties 
                    (id, address, lat, lng, price, bedrooms, bathrooms, 
                     intensity, deal_rating, ai_evaluation_reasoning, property_data, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                    address = EXCLUDED.address,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    price = EXCLUDED.price,
                    bedrooms = EXCLUDED.bedrooms,
                    bathrooms = EXCLUDED.bathrooms,
                    intensity = EXCLUDED.intensity,
                    deal_rating = EXCLUDED.deal_rating,
                    ai_evaluation_reasoning = EXCLUDED.ai_evaluation_reasoning,
                    property_data = EXCLUDED.property_data,
                    timestamp = EXCLUDED.timestamp
                    ''', (
                        prop_id, address, lat, lng, price, bedrooms, bathrooms,
                        intensity, deal_rating, ai_reasoning, 
                        json.dumps(extra_fields) if extra_fields else None,
                        property_data.get('timestamp')
                    ))
            else:
                # SQLite fallback
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR REPLACE INTO properties 
                (id, address, lat, lng, price, bedrooms, bathrooms, 
                 intensity, deal_rating, ai_evaluation_reasoning, property_data, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prop_id, address, lat, lng, price, bedrooms, bathrooms,
                    intensity, deal_rating, ai_reasoning, 
                    json.dumps(extra_fields) if extra_fields else None,
                    property_data.get('timestamp')
                ))
            conn.commit()
        finally:
            conn.close()
        
        # Emit to connected clients
        socketio.emit('new_property', property_data)
        logging.info(f"Property saved and broadcast: {address}")
        
        return jsonify({"status": "success", "message": "Property saved"})
    
    except Exception as e:
        logging.error(f"Error saving property: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/properties', methods=['GET'])
def get_properties():
    try:
        # Parse pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Validate and sanitize inputs
        page = max(1, page)  # Ensure page is at least 1
        per_page = min(100, max(10, per_page))  # Between 10 and 100 items per page
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get filters
        price_min = request.args.get('price_min', type=float)
        price_max = request.args.get('price_max', type=float)
        bedrooms_min = request.args.get('bedrooms_min', type=int)
        intensity_min = request.args.get('intensity_min', type=float)
        
        conn = get_db_connection()
        try:
            properties = []
            total_count = 0
            
            if USE_POSTGRES:
                # PostgreSQL implementation with pagination
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                
                # Build the query with filters
                query = 'SELECT * FROM properties WHERE 1=1'
                count_query = 'SELECT COUNT(*) FROM properties WHERE 1=1'
                params = []
                
                if price_min is not None:
                    query += ' AND price >= %s'
                    count_query += ' AND price >= %s'
                    params.append(price_min)
                
                if price_max is not None:
                    query += ' AND price <= %s'
                    count_query += ' AND price <= %s'
                    params.append(price_max)
                
                if bedrooms_min is not None:
                    query += ' AND bedrooms >= %s'
                    count_query += ' AND bedrooms >= %s'
                    params.append(bedrooms_min)
                
                if intensity_min is not None:
                    query += ' AND intensity >= %s'
                    count_query += ' AND intensity >= %s'
                    params.append(intensity_min)
                
                # Add pagination
                query += ' ORDER BY timestamp DESC LIMIT %s OFFSET %s'
                params.extend([per_page, offset])
                
                # Get total count
                cursor.execute(count_query, params[:-2] if params else None)
                total_count = cursor.fetchone()[0]
                
                # Execute the main query
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    prop = dict(row)
                    
                    # Parse property_data JSON
                    if prop['property_data']:
                        # Already JSON in PostgreSQL, just need to convert to dict
                        if isinstance(prop['property_data'], str):
                            extra_data = json.loads(prop['property_data'])
                        else:
                            extra_data = prop['property_data']
                            
                        # Merge extra data
                        for key, value in extra_data.items():
                            prop[key] = value
                        del prop['property_data']
                    
                    # Ensure lat/lng are available
                    if 'latitude' in prop and 'lat' not in prop:
                        prop['lat'] = prop['latitude']
                    if 'longitude' in prop and 'lng' not in prop:
                        prop['lng'] = prop['longitude']
                    
                    properties.append(prop)
            else:
                # SQLite implementation with pagination
                import sqlite3
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Build the query with filters
                query = 'SELECT * FROM properties WHERE 1=1'
                count_query = 'SELECT COUNT(*) FROM properties WHERE 1=1'
                params = []
                
                if price_min is not None:
                    query += ' AND price >= ?'
                    count_query += ' AND price >= ?'
                    params.append(price_min)
                
                if price_max is not None:
                    query += ' AND price <= ?'
                    count_query += ' AND price <= ?'
                    params.append(price_max)
                
                if bedrooms_min is not None:
                    query += ' AND bedrooms >= ?'
                    count_query += ' AND bedrooms >= ?'
                    params.append(bedrooms_min)
                
                if intensity_min is not None:
                    query += ' AND intensity >= ?'
                    count_query += ' AND intensity >= ?'
                    params.append(intensity_min)
                
                # Add pagination
                query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
                params.extend([per_page, offset])
                
                # Get total count
                cursor.execute(count_query, params[:-2] if params else None)
                total_count = cursor.fetchone()[0]
                
                # Execute the main query
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    prop = dict(row)
                    
                    # Parse property_data JSON
                    if prop['property_data']:
                        extra_data = json.loads(prop['property_data'])
                        # Merge extra data
                        for key, value in extra_data.items():
                            prop[key] = value
                        del prop['property_data']
                    
                    # Ensure lat/lng are available
                    if 'latitude' in prop and 'lat' not in prop:
                        prop['lat'] = prop['latitude']
                    if 'longitude' in prop and 'lng' not in prop:
                        prop['lng'] = prop['longitude']
                    
                    properties.append(prop)
            
            # Prepare pagination metadata
            total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
            
            # Return paginated response
            return jsonify({
                "properties": properties,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            })
        finally:
            conn.close()
    
    except Exception as e:
        logging.error(f"Error getting properties: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    try:
        conn = get_db_connection()
        try:
            if USE_POSTGRES:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM properties')
                total = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.8')
                hot_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.6 AND intensity <= 0.8')
                good_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.4 AND intensity <= 0.6')
                avg_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity <= 0.4')
                weak_deals = cursor.fetchone()[0]
            else:
                # SQLite fallback
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM properties')
                total = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.8')
                hot_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.6 AND intensity <= 0.8')
                good_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity > 0.4 AND intensity <= 0.6')
                avg_deals = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM properties WHERE intensity <= 0.4')
                weak_deals = cursor.fetchone()[0]
            
            return jsonify({
                "total_properties": total,
                "hot_deals": hot_deals,
                "good_deals": good_deals,
                "average_deals": avg_deals,
                "weak_deals": weak_deals,
                "server_time": time.time()
            })
        finally:
            conn.close()
    
    except Exception as e:
        logging.error(f"Error getting status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    logging.info(f"Client connected: {request.sid}")
    emit('connection_status', {'status': 'connected'})

# Initialize database when the module is loaded
# This ensures the database is initialized whether run directly or by Gunicorn
init_db()

# This allows Gunicorn to import the app object for the production server
# The app object needs to be accessible at the module level for Gunicorn to work

if __name__ == '__main__':
    # This block only executes when the script is run directly, not when imported by Gunicorn
    port = int(os.environ.get("PORT", 5005))
    host = '0.0.0.0'
    logging.info(f"Starting fixed backend server on http://{host}:{port}")
    # Write PID to file for easy termination (in development)
    try:
        with open('backend.pid', 'w') as f:
            f.write(str(os.getpid()))
    except:
        logging.warning("Could not write PID file (normal in production)")
    # Run with production settings when deployed
    if IS_PRODUCTION:
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    else:
        socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
