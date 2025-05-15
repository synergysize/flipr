# Fixing WebSocket Connectivity on Render

This guide explains how to fix WebSocket (Socket.IO) connectivity issues in the Flipr backend when deployed to Render.

## The Problem

The frontend at https://app.flipr.realty is unable to establish a WebSocket connection to the backend at https://flipr-backend.onrender.com. The connection attempts result in errors like:

```
Firefox can't establish a connection to the server at wss://flipr-backend.onrender.com/socket.io/?EIO=4&transport=websocket
```

## Root Causes

1. **Incorrect Server Startup Method**: The backend was started with `python fixed_backend.py` instead of using Gunicorn with eventlet worker.

2. **Missing WebSocket Support in Render Configuration**: The `render.yaml` didn't specify the correct startup command for WebSocket support.

3. **Socket.IO Configuration Issues**: Socket.IO requires specific settings for Render compatibility.

## The Solution

### 1. Update `render.yaml`

Replace the existing `render.yaml` with:

```yaml
# Render deployment configuration
services:
- type: web
  name: flipr-7
  runtime: python
  repo: https://github.com/synergysize/flipr
  plan: free
  envVars:
  - key: DATABASE_URL
    sync: false
  - key: DISABLE_SQLITE_FALLBACK
    value: "true"
    sync: false
  - key: PRODUCTION
    value: "true"
    sync: false
  region: oregon
  buildCommand: pip install -r requirements.txt
  startCommand: gunicorn --worker-class eventlet -w 1 fixed_backend:app
  autoDeployTrigger: commit
version: "1"
```

### 2. Ensure Proper Socket.IO Configuration

In `fixed_backend.py`, make sure Socket.IO is configured with:

```python
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",  # Allows connections from any origin
    async_mode='eventlet',     # Required for WebSockets
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)
```

### 3. Use `socketio.run()` for Local Development

For local development, always use:

```python
if __name__ == '__main__':
    # Try to use eventlet monkey patching
    try:
        import eventlet
        eventlet.monkey_patch()
    except ImportError:
        pass
        
    socketio.run(app, host='0.0.0.0', port=PORT)
```

### 4. Frontend Configuration

Ensure the frontend connects with fallback options:

```javascript
socket = io(BACKEND_URL, {
    transports: ['websocket', 'polling'],
    withCredentials: true 
});
```

## Verification

1. Deploy the updated backend to Render.
2. Check that the Socket.IO endpoint responds with a 101 Switching Protocols:
   ```
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" https://flipr-backend.onrender.com/socket.io/?EIO=4&transport=websocket
   ```
3. Run the test client to confirm connectivity:
   ```
   python test_socket_client.py
   ```
4. Open the frontend at https://app.flipr.realty and verify the WebSocket connection.

## Debug Tips

If issues persist:

1. Check Render logs for any errors related to WebSocket connections.
2. Verify that the Gunicorn eventlet worker is running (in the logs).
3. Try enabling CORS for all origins temporarily.
4. Test with a simple Socket.IO example before integrating with the full backend.