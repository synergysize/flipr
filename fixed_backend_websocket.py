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

# Allow specific origins for CORS
ALLOWED_ORIGINS = [
    "https://flipr-app.vercel.app",
    "https://app.flipr.realty",
    "http://app.flipr.realty",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://flipr-5.onrender.com",
    "https://flipr-6.onrender.com",
    "https://flipr-7.onrender.com",
    "*"  # Allow all origins for development/testing
]

CORS(app, origins=ALLOWED_ORIGINS)

# CRITICAL FIX FOR WEBSOCKET SUPPORT:
# - Use eventlet async_mode for Render compatibility
# - Allow all origins for Socket.IO to prevent CORS issues
# - Enable logging for Socket.IO to help with debugging
# - Increase ping timeout and interval for reliable connections
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Database Configuration
# Set the Supabase pooler URL
SUPABASE_POOLER_URL = "postgresql://synergysize:GX0JblzDEbyYxi6k@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

# Use the pooler URL by default, or let the environment override it
DB_URL = os.environ.get("DATABASE_URL", SUPABASE_POOLER_URL)

# Log which database URL we're using
if DB_URL == SUPABASE_POOLER_URL:
    logging.info("Using Supabase connection pooler URL (aws-0-us-east-1.pooler.supabase.com)")
else:
    logging.info("Using DATABASE_URL from environment")
    # Safety check - if environment URL contains the old host, replace it with the pooler
    if "db.utalravvcgiehxojrgba.supabase.co" in DB_URL:
        old_url = DB_URL
        DB_URL = DB_URL.replace("db.utalravvcgiehxojrgba.supabase.co", "aws-0-us-east-1.pooler.supabase.com")
        logging.warning(f"Replaced old Supabase host with pooler host in DATABASE_URL")
        logging.warning(f"Old URL: {old_url}")
        logging.warning(f"New URL: {DB_URL}")

# Database URL validation and cleanup
if DB_URL:
    # Remove var name if someone included it (DATABASE_URL=)
    if DB_URL.startswith("DATABASE_URL="):
        DB_URL = DB_URL.split("=", 1)[1]
        logging.info(f"Removed 'DATABASE_URL=' prefix from connection string")

    # Fix newlines in the URL (common copy-paste issue)
    DB_URL = DB_URL.replace("\n", "").replace("\r", "")
    
    # Validate DATABASE_URL format
    try:
        # Check that it starts with postgres:// or postgresql:// and has at least one /@
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

# Always use PostgreSQL with our default connection
logging.info(f"Database connection configured to use PostgreSQL")

# Database connection file
DB_FILE = "properties.db"

def get_db_connection():
    """Get database connection (PostgreSQL)"""
    if USE_POSTGRES:
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
    else:
        # Fallback to SQLite (should be disabled in production)
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

@app.route('/healthz')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "ok",
        "server": "Flipr Backend",
        "version": "1.0.0",
        "socketio": "enabled",
        "database": "PostgreSQL" if USE_POSTGRES else "SQLite"
    })

@app.route('/update', methods=['POST'])
def update_property():
    try:
        property_data = request.json
        
        # Ensure standard coordinates format
        if 'latitude' in property_data and 'lat' not in property_data:
            property_data['lat'] = property_data['latitude']
        if 'longitude' in property_data and 'lng' not in property_data:
            property_data['lng'] = property_data['longitude']
        
        # Generate a unique ID if not provided
        if 'id' not in property_data:
            property_data['id'] = str(uuid.uuid4())
            
        # Add timestamp if not provided
        if 'timestamp' not in property_data:
            property_data['timestamp'] = int(time.time())
            
        property_id = property_data['id']
        address = property_data.get('address', 'Unknown')
        lat = property_data.get('lat')
        lng = property_data.get('lng')
        price = property_data.get('price')
        bedrooms = property_data.get('bedrooms')
        bathrooms = property_data.get('bathrooms')
        intensity = property_data.get('intensity', 0.0)
        deal_rating = property_data.get('deal_rating', 'Unknown')
        ai_evaluation_reasoning = property_data.get('ai_evaluation_reasoning', '')
        timestamp = property_data.get('timestamp')
        
        # Store in database
        with get_db_connection() as conn:
            try:
                if USE_POSTGRES:
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO properties 
                    (id, address, lat, lng, price, bedrooms, bathrooms, intensity, deal_rating, ai_evaluation_reasoning, property_data, timestamp)
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
                        property_id, address, lat, lng, price, bedrooms, bathrooms, intensity, 
                        deal_rating, ai_evaluation_reasoning, json.dumps(property_data), timestamp
                    ))
                else:
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT OR REPLACE INTO properties 
                    (id, address, lat, lng, price, bedrooms, bathrooms, intensity, deal_rating, ai_evaluation_reasoning, property_data, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        property_id, address, lat, lng, price, bedrooms, bathrooms, intensity, 
                        deal_rating, ai_evaluation_reasoning, json.dumps(property_data), timestamp
                    ))
                conn.commit()
                
                # Emit the new property event to all connected clients via Socket.IO
                # This allows real-time updates in the frontend
                socketio.emit('new_property', property_data)
                
                return jsonify({"status": "success", "id": property_id})
            except Exception as e:
                logging.error(f"Database error while saving property: {str(e)}")
                conn.rollback()
                return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Error processing property update: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/properties', methods=['GET'])
def get_properties():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        with get_db_connection() as conn:
            if USE_POSTGRES:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute('''
                SELECT * FROM properties 
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                ''', (per_page, offset))
            else:
                conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
                cursor = conn.cursor()
                cursor.execute('''
                SELECT * FROM properties 
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                ''', (per_page, offset))
            
            properties = cursor.fetchall()
            
            # For PostgreSQL, convert DictRow objects to dicts
            if USE_POSTGRES:
                properties = [dict(row) for row in properties]
            
            # Parse property_data JSON strings
            for prop in properties:
                try:
                    if 'property_data' in prop and prop['property_data']:
                        if isinstance(prop['property_data'], str):
                            prop['property_data'] = json.loads(prop['property_data'])
                except Exception as e:
                    logging.error(f"Error parsing property_data JSON: {str(e)}")
                    prop['property_data'] = {}
            
            return jsonify(properties)
    except Exception as e:
        logging.error(f"Error fetching properties: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logging.info(f"Client connected: {request.sid}")
    emit('connection_status', {
        'status': 'connected',
        'message': 'Successfully connected to Flipr WebSocket server',
        'sid': request.sid
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnect"""
    logging.info(f"Client disconnected: {request.sid}")

@socketio.on('ping_test')
def handle_ping(data):
    """Simple ping/pong test"""
    logging.info(f"Received ping from {request.sid}: {data}")
    emit('pong_response', {
        'received': data,
        'message': 'Pong response from Flipr server',
        'timestamp': time.time()
    })

# Initialize database when the module is loaded
# This ensures the database is initialized whether run directly or by Gunicorn
init_db()

# This allows Gunicorn to import the app object for the production server
# The app object needs to be accessible at the module level for Gunicorn to work

if __name__ == '__main__':
    # This block only executes when the script is run directly, not when imported by Gunicorn
    port = int(os.environ.get("PORT", 5005))
    host = '0.0.0.0'
    logging.info(f"Starting Flipr backend server on http://{host}:{port}")
    
    # Write PID to file for easy termination (in development)
    try:
        with open('backend.pid', 'w') as f:
            f.write(str(os.getpid()))
    except:
        logging.warning("Could not write PID file (normal in production)")
    
    # Try to use eventlet monkey patching when running directly
    try:
        import eventlet
        eventlet.monkey_patch()
        logging.info("Applied eventlet monkey patching for WebSocket support")
    except ImportError:
        logging.warning("Eventlet not available, WebSockets may not work correctly")
    
    # Run with production settings when deployed
    # CRITICAL: Use socketio.run, NOT app.run for WebSocket support
    if IS_PRODUCTION:
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    else:
        socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)