#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Kill any previous instances
pkill -f "cloudflared tunnel" 2>/dev/null || true
if lsof -ti:5055 > /dev/null 2>&1; then
  lsof -ti:5055 | xargs kill -9 2>/dev/null || true
fi
sleep 1

# Start Flask app
echo "Starting Flask app on port 5055..."
nohup "$DIR/.venv-modern/bin/python" app.py > server.log 2>&1 &
APP_PID=$!
echo $APP_PID > server.pid

# Wait for port 5055 to become active
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:5055/api/session > /dev/null; then
    echo "App server is responding on http://127.0.0.1:5055"
    break
  fi
  sleep 0.5
done

# Start cloudflared
echo "Starting Cloudflare tunnel..."
rm -f tunnel.log
nohup /Users/nived/.local/bin/cloudflared tunnel --url http://127.0.0.1:5055 > tunnel.log 2>&1 &
TUNNEL_PID=$!
echo $TUNNEL_PID > tunnel.pid

# Wait for Cloudflare URL
TUNNEL_URL=""
for i in $(seq 1 40); do
  TUNNEL_URL=$(grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' tunnel.log | tail -n 1 || true)
  if [ -n "$TUNNEL_URL" ]; then
    echo "ACTIVE_URL: $TUNNEL_URL"
    break
  fi
  sleep 0.5
done

if [ -z "$TUNNEL_URL" ]; then
  echo "Failed to get tunnel URL within timeout. Check tunnel.log"
  cat tunnel.log
  exit 1
fi
