#!/bin/bash

# Log file
LOGFILE=/home/israelf/Desktop/TelescopeWatcher_linux_side/startup.log

{
    echo "========== Startup script started at $(date) =========="


    # Change to working directory
    cd /home/israelf/Desktop/TelescopeWatcher_linux_side

    # Ensure executable
    chmod +x ./Others/mediamtx/mediamtx

    # Kill any existing
    pkill -f mediamtx
    pkill -f RunServer.py
    sleep 1

    # Start mediamtx
    echo "Starting mediamtx..."
    (cd Others/mediamtx && ./mediamtx) >> /home/israelf/Desktop/TelescopeWatcher_linux_side/mediamtx.log 2>&1 &

    # Wait for port
    for i in {1..20}; do
        if ss -tuln | grep -q ':8554'; then
            echo "mediamtx is ready on port 8554"
            break
        fi
        sleep 0.5
    done

    # Start Python
    echo "Starting Python server..."
    python3 /home/israelf/Desktop/TelescopeWatcher_linux_side/RunServer.py >> /home/israelf/Desktop/TelescopeWatcher_linux_side/myscript.log 2>&1 &

    sleep 2

    # Verify
    if pgrep -f mediamtx > /dev/null; then
        echo "✓ mediamtx is running (PID: $(pgrep -f mediamtx))"
    else
        echo "✗ mediamtx is NOT running!"
    fi

    if pgrep -f RunServer.py > /dev/null; then
        echo "✓ Python server is running (PID: $(pgrep -f RunServer.py))"
    else
        echo "✗ Python server is NOT running!"
    fi

    echo "========== Startup script completed at $(date) =========="
} >> "$LOGFILE" 2>&1

# Exit to tell systemd we're done forking
exit 0
