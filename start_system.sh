#!/bin/bash

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
