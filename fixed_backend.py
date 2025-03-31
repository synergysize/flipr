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
    "http://localhost:3000",         # For local development
    "http://localhost:5173"          # For local Vite development
]

CORS(app, origins=ALLOWED_ORIGINS)
socketio = SocketIO(app, cors_allowed_origins=ALLOWED_ORIGINS)

# Database configuration - Supabase PostgreSQL
DB_URL = os.environ.get("DATABASE_URL", "")  # Get from environment variable

# Fallback to SQLite for development if no PostgreSQL URL is provided
USE_POSTGRES = bool(DB_URL)
DB_FILE = "properties.db"

def get_db_connection():
    """Get database connection (either PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(DB_URL)
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
        standard_fields = ['id', 'address', 'lat', 'lng', 'price', 'bedrooms', 
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
    port = int(os.environ.get("PORT", 5001))
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
        socketio.run(app, host=host, port=port, debug=False)
    else:
        socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
