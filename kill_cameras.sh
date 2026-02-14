#!/bin/bash
echo "Stopping all camera streams and servers..."

# 1. Kill streaming tools directly accessing hardware
sudo pkill -9 -f mjpg_streamer
sudo pkill -9 -f ffmpeg

# 2. Kill MediaMTX (RTSP Server)
sudo pkill -f mediamtx

# 3. Kill Python scripts that might be running the server or tests
# Be specific to avoid killing system tools or VS Code server components
pkill -f RunServer.py
pkill -f test_camera_rotation.py
pkill -f UnifiedServer

echo "Wait a moment for devices to release..."
sleep 2

# Check if anything is left using video0 (if fuser installed)
if command -v fuser &> /dev/null; then
    sudo fuser -k -v /dev/video0
fi

echo "Cleanup complete."
