import socketio
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Create Socket.IO client
sio = socketio.Client(logger=True, engineio_logger=True)

# Define event handlers
@sio.event
def connect():
    logging.info("Connected to server!")

@sio.event
def disconnect():
    logging.info("Disconnected from server!")

@sio.event
def connect_error(error):
    logging.error(f"Connection error: {error}")

@sio.event
def connection_status(data):
    logging.info(f"Received connection status: {data}")

@sio.event
def pong_response(data):
    logging.info(f"Received pong: {data}")

def test_connection(server_url):
    """Test connection to the specified server"""
    logging.info(f"Testing connection to: {server_url}")
    
    try:
        # Connect to the server with both WebSocket and polling transports
        # This ensures fallback to polling if WebSocket fails
        sio.connect(
            server_url,
            transports=["websocket", "polling"],
            wait_timeout=10
        )
        
        # Wait for connection
        time.sleep(1)
        
        # Send a ping test
        if sio.connected:
            logging.info("Sending ping test...")
            sio.emit('ping_test', {'message': 'Hello from client', 'timestamp': time.time()})
            time.sleep(2)  # Wait for response
        
        # Disconnect
        sio.disconnect()
        
        return True
    except Exception as e:
        logging.error(f"Connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test with the Render deployed backend
    render_server = "https://flipr-backend.onrender.com"
    logging.info(f"Testing connection to Render server: {render_server}")
    if test_connection(render_server):
        logging.info("Connection to Render server successful!")
    else:
        logging.error("Connection to Render server failed!")
        
    # Test with local development server
    local_server = "http://localhost:5005"
    logging.info(f"\nTesting connection to local server: {local_server}")
    if test_connection(local_server):
        logging.info("Connection to local server successful!")
    else:
        logging.error("Connection to local server failed!")