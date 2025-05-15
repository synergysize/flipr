# Flipr WebSocket Deployment Checklist

## Files to Deploy

- [x] `render.yaml` - With correct WebSocket configuration:
  ```yaml
  startCommand: gunicorn --worker-class eventlet -w 1 fixed_backend_websocket:app
  ```

- [x] `fixed_backend_websocket.py` - Socket.IO enabled backend
  - Properly initializes SocketIO with eventlet worker
  - Includes all necessary event handlers
  - Uses socketio.run() for server startup

## Required Environment Variables

```
DATABASE_URL=postgresql://postgres:GX0JblzDEbyYxi6k@aws-0-us-east-1.pooler.supabase.com:5432/postgres
PRODUCTION=true
DISABLE_SQLITE_FALLBACK=true
SUPABASE_URL=https://utalravvcgiehxojrgba.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Deployment Steps

1. Commit the updated files to GitHub:
   ```bash
   git add render.yaml fixed_backend_websocket.py
   git commit -m "Fix WebSocket connectivity with Socket.IO and eventlet"
   git push
   ```

2. Deploy to Render:
   - Login to the Render dashboard
   - Select the Flipr backend service
   - Go to Settings
   - Verify the build command is `pip install -r requirements.txt`
   - Verify the start command is `gunicorn --worker-class eventlet -w 1 fixed_backend_websocket:app`
   - Click "Manual Deploy" > "Deploy latest commit"

## Verification Steps

1. **Server Response Check**:
   ```bash
   curl https://flipr-backend.onrender.com/healthz
   ```
   Expected response: JSON with `"socketio": "enabled"`

2. **WebSocket Handshake Test**:
   ```bash
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" https://flipr-backend.onrender.com/socket.io/?EIO=4&transport=websocket
   ```
   Expected: HTTP/1.1 101 Switching Protocols

3. **Socket.IO Client Test**:
   ```bash
   python test_socket_client.py
   ```
   Expected: "Connection to Render server successful!"

4. **Frontend Integration Test**:
   - Open https://app.flipr.realty in browser
   - Open developer tools (F12) > Network tab
   - Filter by "WS" to show WebSocket connections
   - Verify connection to wss://flipr-backend.onrender.com/socket.io/?EIO=4&transport=websocket
   - Check Console for absence of WebSocket connection errors
   - Verify "Connected" status in the UI

## Troubleshooting

If WebSocket connections still fail:

1. Check Render logs for any errors
2. Verify the service is deployed as a Web Service (not Background Worker)
3. Ensure all required dependencies are installed:
   ```
   Flask-SocketIO==5.3.6
   eventlet==0.33.3
   ```
4. Confirm that CORS settings are correctly allowing the frontend origin
5. Try enabling verbose logging in Socket.IO for debugging