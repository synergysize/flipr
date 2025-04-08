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
    "https://flipr-6.onrender.com"
]

CORS(app, origins=ALLOWED_ORIGINS)
socketio = SocketIO(app, cors_allowed_origins=ALLOWED_ORIGINS)

# Get from environment variable
DB_URL = os.environ.get("DATABASE_URL", "")

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

# Fallback to SQLite for development if no PostgreSQL URL is provided
USE_POSTGRES = bool(DB_URL)
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
            logging.info("Falling back to SQLite database")
            # Use nonlocal would be better but we're at module level
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
            logging.info("SQLite database initialized (fallback mode)")
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
        conn = get_db_connection()
        try:
            properties = []
            
            if USE_POSTGRES:
                # PostgreSQL implementation
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute('SELECT * FROM properties')
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
                # SQLite implementation
                import sqlite3
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM properties')
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
            
            return jsonify(properties)
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

# Replace with:
 if __name__ == '__main__':
    init_db()
    # Get port from environment variable for compatibility with hosting services
    # Use a different port to avoid conflicts
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
     if os.environ.get("PRODUCTION") == "true":
         socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
     else:
         socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
