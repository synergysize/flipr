from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import os
import time
import shutil
import threading
import datetime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'property_data.json')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

# Create backup directory if it doesn't exist
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return []

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=2)

def create_backup():
    """Create a backup of the property data file"""
    if os.path.exists(DATA_FILE):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f'property_data_backup_{timestamp}.json')
        shutil.copy2(DATA_FILE, backup_file)
        print(f"Created backup: {backup_file}")
        return backup_file
    return None

def periodic_backup():
    """Function to run periodic backups every 10 minutes"""
    while True:
        create_backup()
        time.sleep(600)  # 10 minutes in seconds

# Start the backup thread
backup_thread = threading.Thread(target=periodic_backup, daemon=True)
backup_thread.start()

@app.route('/update', methods=['POST'])
def update_properties():
    property_data = request.json
    data = load_data()
    
    # Add id to property for tracking
    property_id = len(data) + 1
    property_data['id'] = property_id
    
    # Add timestamp
    property_data['timestamp'] = time.time()
    
    # Transform nested data structure to flat structure for UI
    # Extract bedrooms and bathrooms from rooms
    if 'rooms' in property_data and isinstance(property_data['rooms'], dict):
        if 'beds' in property_data['rooms']:
            property_data['bedrooms'] = property_data['rooms']['beds']
        if 'baths' in property_data['rooms']:
            property_data['bathrooms'] = property_data['rooms']['baths']
    
    # Extract price information if available
    if 'saleAmount' in property_data:
        property_data['price'] = property_data['saleAmount']
    elif 'price' not in property_data and 'buildingSize' in property_data and 'size' in property_data['buildingSize']:
        # If no direct price, estimate based on size as a placeholder
        sqft = property_data['buildingSize']['size']
        if sqft > 0:
            property_data['estimated_price'] = sqft * 300  # Simple price estimation
    
    # Add to data
    data.append(property_data)
    save_data(data)
    
    # Create a backup if we've added a significant number of properties
    # (every 10 new properties)
    if property_id % 10 == 0:
        backup_file = create_backup()
        print(f"Created milestone backup after {property_id} properties: {backup_file}")
    
    # Emit real-time update through WebSocket
    socketio.emit('new_property', property_data)
    
    return jsonify({"message": "Data received", "status": "success", "property_id": property_id})

@app.route('/properties', methods=['GET'])
def get_properties():
    data = load_data()
    
    # Transform all existing properties to have the correct structure for UI
    for prop in data:
        # Extract bedrooms and bathrooms from rooms if not already present
        if 'bedrooms' not in prop and 'rooms' in prop and isinstance(prop['rooms'], dict):
            if 'beds' in prop['rooms']:
                prop['bedrooms'] = prop['rooms']['beds']
        if 'bathrooms' not in prop and 'rooms' in prop and isinstance(prop['rooms'], dict):
            if 'baths' in prop['rooms']:
                prop['bathrooms'] = prop['rooms']['baths']
        
        # Extract price information if not already present
        if 'price' not in prop and 'estimated_price' not in prop:
            if 'saleAmount' in prop:
                prop['price'] = prop['saleAmount']
            elif 'buildingSize' in prop and isinstance(prop['buildingSize'], dict) and 'size' in prop['buildingSize']:
                sqft = prop['buildingSize']['size']
                if sqft and sqft > 0:
                    prop['estimated_price'] = sqft * 300  # Simple price estimation
    
    return jsonify(data)

# Add a route to get a specific property by ID
@app.route('/property/<int:property_id>', methods=['GET'])
def get_property(property_id):
    data = load_data()
    
    for prop in data:
        if prop.get('id') == property_id:
            # Apply the same transformations for consistency
            if 'bedrooms' not in prop and 'rooms' in prop and isinstance(prop['rooms'], dict):
                if 'beds' in prop['rooms']:
                    prop['bedrooms'] = prop['rooms']['beds']
            if 'bathrooms' not in prop and 'rooms' in prop and isinstance(prop['rooms'], dict):
                if 'baths' in prop['rooms']:
                    prop['bathrooms'] = prop['rooms']['baths']
            
            if 'price' not in prop and 'estimated_price' not in prop:
                if 'saleAmount' in prop:
                    prop['price'] = prop['saleAmount']
                elif 'buildingSize' in prop and isinstance(prop['buildingSize'], dict) and 'size' in prop['buildingSize']:
                    sqft = prop['buildingSize']['size']
                    if sqft and sqft > 0:
                        prop['estimated_price'] = sqft * 300  # Simple price estimation
            
            return jsonify(prop)
    
    return jsonify({"error": "Property not found"}), 404

# Add a route to delete a property by ID
@app.route('/property/<int:property_id>', methods=['DELETE'])
def delete_property(property_id):
    data = load_data()
    
    initial_length = len(data)
    data = [prop for prop in data if prop.get('id') != property_id]
    
    if len(data) < initial_length:
        save_data(data)
        return jsonify({"message": f"Property {property_id} deleted", "status": "success"})
    
    return jsonify({"error": "Property not found"}), 404

# Add a route to update a property's AI evaluation
@app.route('/property/<int:property_id>/ai-evaluate', methods=['POST'])
def ai_evaluate_property(property_id):
    data = load_data()
    
    # Find the property
    for prop in data:
        if prop.get('id') == property_id:
            # Update with AI evaluation from request
            evaluation_data = request.json
            
            if 'intensity' in evaluation_data:
                prop['intensity'] = evaluation_data['intensity']
            
            if 'deal_rating' in evaluation_data:
                prop['deal_rating'] = evaluation_data['deal_rating']
            
            if 'ai_evaluation_reasoning' in evaluation_data:
                prop['ai_evaluation_reasoning'] = evaluation_data['ai_evaluation_reasoning']
            
            save_data(data)
            
            # Emit update through WebSocket
            socketio.emit('property_updated', prop)
            
            return jsonify({"message": f"AI evaluation updated for property {property_id}", "property": prop})
    
    return jsonify({"error": "Property not found"}), 404

# Add a route to clear all data (for testing)
@app.route('/clear', methods=['POST'])
def clear_data():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    
    return jsonify({"message": "All property data cleared", "status": "success"})

# Add a route for system status
@app.route('/status', methods=['GET'])
def system_status():
    data = load_data()
    
    # Count properties by rating
    red_deals = 0
    orange_deals = 0
    yellow_deals = 0
    green_deals = 0
    blue_deals = 0
    
    for prop in data:
        intensity = prop.get('intensity', 0.5)
        if intensity > 0.8:
            red_deals += 1
        elif intensity > 0.6:
            orange_deals += 1
        elif intensity > 0.4:
            yellow_deals += 1
        elif intensity > 0.2:
            green_deals += 1
        else:
            blue_deals += 1
    
    status = {
        "total_properties": len(data),
        "red_deals": red_deals,
        "orange_deals": orange_deals,
        "yellow_deals": yellow_deals,
        "green_deals": green_deals,
        "blue_deals": blue_deals,
        "server_time": time.time(),
        "data_file": os.path.abspath(DATA_FILE) if os.path.exists(DATA_FILE) else None,
        "data_file_size": os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    }
    
    return jsonify(status)

if __name__ == '__main__':
    port = 5001  # Changed from 5000 to avoid conflicts
    print(f"Starting Flask backend server on http://127.0.0.1:{port}")
    print(f"Data file location: {os.path.abspath(DATA_FILE) if os.path.exists(DATA_FILE) else 'Not created yet'}")
    socketio.run(app, debug=True, port=port, allow_unsafe_werkzeug=True)