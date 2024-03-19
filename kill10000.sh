#!/bin/bash

# Find the process using port 10000
PID=$(lsof -t -i:10000)

# Check if the PID was found
if [ ! -z "$PID" ]; then
    echo "Killing process on port 10000 with PID: $PID"
    kill $PID
else
    echo "No process found on port 10000."
fi

