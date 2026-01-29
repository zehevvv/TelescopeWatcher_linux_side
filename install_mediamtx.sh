#!/bin/bash
# Download and install mediamtx (RTSP Server)
URL="https://github.com/bluenviron/mediamtx/releases/download/v1.15.6/mediamtx_v1.15.6_linux_arm64.tar.gz"
echo "Downloading MediaMTX from $URL..."
wget -q $URL -O mediamtx.tar.gz

if [ $? -eq 0 ]; then
    echo "Extracting..."
    tar -xzf mediamtx.tar.gz
    chmod +x mediamtx
    rm mediamtx.tar.gz
    echo "MediaMTX installed successfully."
    echo "You can run it with: ./mediamtx"
else
    echo "Failed to download MediaMTX."
fi
