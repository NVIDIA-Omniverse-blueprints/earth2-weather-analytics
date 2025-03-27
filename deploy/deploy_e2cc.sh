#!/bin/bash

# Default values
FORCE=false
APP_TYPE="desktop"
CACHE_PATH="$(pwd)/cache"

# Function to validate and create cache directory
validate_cache_path() {
    local path="$1"

    # Check if path exists
    if [ -d "$path" ]; then
        # Check if directory is writable
        if [ -w "$path" ]; then
            echo "Using existing cache directory: $path"
            return 0
        else
            echo "Error: Cache directory exists but is not writable: $path"
            return 1
        fi
    else
        # Try to create the directory
        echo "Creating cache directory: $path"
        if mkdir -p "$path" 2>/dev/null; then
            echo "Successfully created cache directory"
            return 0
        else
            echo "Error: Failed to create cache directory: $path"
            return 1
        fi
    fi
}

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -f, --force         Force clean rebuild by removing _build, _repo and _compiler folders"
    echo "  -d, --desktop       Launch desktop app (default)"
    echo "  -s, --streamer      Launch streamer app"
    echo "  -c, --cache-path    Set custom cache path for the application"
    echo "                      Example: --cache-path /path/to/cache"
    echo "  -h, --help          Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force)
            FORCE=true
            shift
            ;;
        -d|--desktop)
            APP_TYPE="desktop"
            shift
            ;;
        -s|--streamer)
            APP_TYPE="streamer"
            shift
            ;;
        -c|--cache-path)
            if [[ -n "$2" && "$2" != -* ]]; then
                CACHE_PATH="$2"
                shift 2
            else
                echo "Error: --cache-path/-c requires a path argument"
                exit 1
            fi
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "Using cache path: ${CACHE_PATH}"
if ! validate_cache_path "$CACHE_PATH"; then
    echo "Cache path validation failed. Exiting."
    exit 1
fi

# Force clean if requested
if [ "$FORCE" = true ]; then
    echo "Forcing clean rebuild..."
    rm -rf e2cc/_build e2cc/_repo e2cc/_compiler
fi

# Build the application
echo "Building application..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    ./e2cc/build.bat --release --no-docker
else
    ./e2cc/build.sh --release --no-docker
fi

# Check if build was successful
if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

sleep 1

# Set cache path environment variable if provided
if [ -n "$CACHE_PATH" ]; then
    echo "Setting E2CC_CACHE_PATH to: $CACHE_PATH"
    export E2CC_CACHE_PATH="$CACHE_PATH"
fi

# Launch the appropriate app
if [ "$APP_TYPE" = "desktop" ]; then
    echo "Launching omniverse desktop app..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        ./e2cc/_build/windows-x86_64/release/omni.earth_2_command_center.app_desktop.bat
    else
        ./e2cc/_build/linux-x86_64/release/omni.earth_2_command_center.app_desktop.sh
    fi
else
    echo "Launching omniverse streamer app..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        ./e2cc/_build/windows-x86_64/release/omni.earth_2_command_center.app_streamer.bat
    else
        ./e2cc/_build/linux-x86_64/release/omni.earth_2_command_center.app_streamer.sh
    fi
fi
