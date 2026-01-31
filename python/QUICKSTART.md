# iFit CLI Quick Start Guide

## Installation

1. Navigate to the Python directory:
   ```bash
   cd python
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

3. Verify installation:
   ```bash
   ifit --help
   ```

## First Steps

### 1. Discover Your Device

Find your iFit equipment using the 4-character BLE code shown on the display:

```bash
ifit discover 1a2b
```

This will output the BLE address (e.g., `AA:BB:CC:DD:EE:FF`) that you'll use for all other commands.

### 2. Get Your Activation Code

**Option A: Automatic Discovery (Recommended)**

Let the tool capture the activation code from your manufacturer's app:

```bash
# Install the required package
pip install bless

# Run discovery
ifit discover-activation 1a2b
```

Then open your manufacturer's app (iFit, NordicTrack, ProForm, etc.) and connect to your equipment. The tool will automatically capture and display the activation code.

See [ACTIVATION_DISCOVERY.md](ACTIVATION_DISCOVERY.md) for detailed instructions.

**Option B: Manual Entry**

If you already have your 8-character activation code, skip to step 3.

### 3. Get Equipment Information

Connect to your device and view its capabilities:

```bash
ifit info AA:BB:CC:DD:EE:FF 12345678
```

Replace:
- `AA:BB:CC:DD:EE:FF` with your device's BLE address (from step 1)
- `12345678` with your activation code (from step 2)

### 4. Monitor Your Workout

See real-time values while exercising:

```bash
ifit monitor AA:BB:CC:DD:EE:FF 12345678
```

Press `Ctrl+C` to stop monitoring.

## Common Use Cases

### Control Your Treadmill from Command Line

```bash
# Start the treadmill
ifit control AA:BB:CC:DD:EE:FF 12345678 start

# Set speed to 5.0 km/h
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5.0

# Set incline to 2%
ifit control AA:BB:CC:DD:EE:FF 12345678 incline --value 2

# Stop the treadmill
ifit control AA:BB:CC:DD:EE:FF 12345678 stop
```

### Read Specific Values

```bash
# Read current workout metrics
ifit read AA:BB:CC:DD:EE:FF 12345678 --current

# Read specific characteristics
ifit read AA:BB:CC:DD:EE:FF 12345678 Kph Incline Pulse

# Get JSON output for scripting
ifit read AA:BB:CC:DD:EE:FF 12345678 --current --json
```

### Use with Zwift or Other FTMS Apps

Run the FTMS relay server to make your iFit equipment compatible with apps like Zwift:

```bash
ifit ftms AA:BB:CC:DD:EE:FF 12345678 --name "My Treadmill"
```

The server will advertise as a FTMS-compatible device that Zwift can connect to.

## Advanced Usage

### Scripting and Automation

You can use the JSON output mode for scripting:

```bash
# Get current speed in a script
SPEED=$(ifit read AA:BB:CC:DD:EE:FF 12345678 --current --json | jq -r '.CurrentKph')
echo "Current speed: $SPEED km/h"
```

### List All Capabilities

See what your equipment supports:

```bash
ifit capabilities AA:BB:CC:DD:EE:FF 12345678
```

### Write Multiple Values

Change multiple settings at once:

```bash
ifit write AA:BB:CC:DD:EE:FF 12345678 Kph=6.5 Incline=3 Mode=1
```

## Troubleshooting

### Device Not Found

- Make sure Bluetooth is enabled on your computer
- Ensure the equipment is powered on and in pairing mode
- Check that you're using the correct 4-character BLE code
- Try increasing the timeout: `ifit discover 1a2b --timeout 20`

### Connection Issues

- Verify the BLE address is correct
- Ensure the activation code matches your equipment
- Check that no other app is connected to the equipment
- Try restarting the equipment

### Permission Errors (Linux)

On Linux, you may need to run with sudo or add your user to the `bluetooth` group:

```bash
sudo usermod -a -G bluetooth $USER
```

Then log out and back in.

## Getting Help

For detailed help on any command:

```bash
ifit <command> --help
```

For example:
```bash
ifit control --help
ifit ftms --help
```
