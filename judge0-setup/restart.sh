#!/bin/bash
# Restart Judge0 services

cd "$(dirname "$0")"

echo "Restarting Judge0..."
./stop.sh
sleep 3
./start.sh
