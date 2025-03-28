from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import os
import time

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_FILE = 'property_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return []

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=2)

@app.route('/update', methods=['POST'])
def update_properties():
    property_data = request.json
    data = load_data()
    
    # Add id to property for tracking
    property_id = len(data) + 1
    property_data['id'] = property_id
    
    # Add timestamp
    property_data['timestamp'] = time.time()
    
    # Add to data
    data.append(property_data)
    save_data(data)
    
    # Emit real-time update through WebSocket
    socketio.emit('new_property', property_data)
    
    return jsonify({"message": "Data received", "status": "success", "property_id": property_id})

@app.route('/properties', methods=['GET'])
def get_properties():
    data = load_data()
    return jsonify(data)

# Add a route to get a specific property by ID
@app.route('/property/<int:property_id>', methods=['GET'])
def get_property(property_id):
    data = load_data()
    
    for prop in data:
        if prop.get('id') == property_id:
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
    hot_deals = 0
    good_deals = 0
    average_deals = 0
    weak_deals = 0
    
    for prop in data:
        intensity = prop.get('intensity', 0.5)
        if intensity > 0.8:
            hot_deals += 1
        elif intensity > 0.6:
            good_deals += 1
        elif intensity > 0.4:
            average_deals += 1
        else:
            weak_deals += 1
    
    status = {
        "total_properties": len(data),
        "hot_deals": hot_deals,
        "good_deals": good_deals,
        "average_deals": average_deals,
        "weak_deals": weak_deals,
        "server_time": time.time(),
        "data_file": os.path.abspath(DATA_FILE) if os.path.exists(DATA_FILE) else None,
        "data_file_size": os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    }
    
    return jsonify(status)

if __name__ == '__main__':
    print(f"Starting Flask backend server on http://127.0.0.1:5000")
    print(f"Data file location: {os.path.abspath(DATA_FILE) if os.path.exists(DATA_FILE) else 'Not created yet'}")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow
