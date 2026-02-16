#!/bin/bash

# Kill any existing processes on required ports
for PORT in 8000 5173; do
    PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Port $PORT in use (PID $PID) — killing..."
        kill -9 $PID 2>/dev/null
        sleep 0.5
    fi
done

# Activate virtual environment
source .venv/bin/activate

# Start backend in background
echo "Starting Backend..."
python backend/server.py &
BACKEND_PID=$!

# Start frontend
echo "Starting Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT SIGTERM

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
