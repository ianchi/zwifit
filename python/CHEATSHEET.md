# iFit CLI Cheat Sheet

Quick reference for common commands.

## Installation
```bash
cd python && pip install -e .
```

## Device Discovery
```bash
ifit discover <ble-code>
ifit discover 1a2b --timeout 20
```

## Activation Code Discovery
```bash
# Automatic discovery (requires manufacturer app)
ifit discover-activation <ble-code>
ifit discover-activation 1a2b --address AA:BB:CC:DD:EE:FF --timeout 60

# This intercepts the activation code from your manufacturer's app
# 1. Run the command
# 2. Open manufacturer app and connect to your equipment
# 3. The activation code will be captured automatically
```

## Information & Capabilities
```bash
ifit info <address> <code>                    # Basic info
ifit info <address> <code> -v                  # Verbose
ifit capabilities <address> <code>             # List capabilities
```

## Reading Values
```bash
ifit read <address> <code> --current           # Current workout values
ifit read <address> <code> Kph Incline Pulse   # Specific characteristics
ifit read <address> <code> --current --json    # JSON output
```

## Writing Values
```bash
ifit write <address> <code> Kph=5.0            # Single value
ifit write <address> <code> Kph=6 Incline=2    # Multiple values
```

## Treadmill Control
```bash
ifit control <address> <code> start                    # Start
ifit control <address> <code> stop                     # Stop
ifit control <address> <code> speed --value 5.0        # Set speed (km/h)
ifit control <address> <code> incline --value 2        # Set incline (%)
ifit control <address> <code> calibrate-incline        # Calibrate
```

## Monitoring
```bash
ifit monitor <address> <code>                  # Monitor (1s interval)
ifit monitor <address> <code> --interval 0.5   # Custom interval
```

## FTMS Relay (for Zwift, etc.)
```bash
ifit ftms <address> <code>                                 # Basic
ifit ftms <address> <code> --name "My Treadmill"           # Custom name
ifit ftms <address> <code> --name "Treadmill" --interval 1 # All options
```

## Quick Examples

### First Time Setup
```bash
# 1. Find device
ifit discover 1a2b

# 2. Get activation code automatically (recommended)
ifit discover-activation 1a2b
# Then open your manufacturer's app and connect

# 3. Or manually if you already have the activation code
# Connect and check
ifit info AA:BB:CC:DD:EE:FF 12345678 -v

# 4. Test control
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 3.0
```

### Getting Your Activation Code

**Option 1: Automatic Discovery (Recommended)**
```bash
ifit discover-activation 1a2b
```
This creates a BLE proxy that captures the activation code when you connect via the manufacturer's app.

**Option 2: Manual Entry**
If you already have an 8-character hex activation code from another source, use it directly with commands.

**What is the activation code?**
- The BLE code (4 chars like "1a2b") is shown on your treadmill display
- The activation code (8 hex chars like "12345678") is sent by the manufacturer's app during connection
- It's different from the BLE code and is required to control the equipment

### Quick Workout
```bash
# Start at 4 km/h, 0% incline
ifit write AA:BB:CC:DD:EE:FF 12345678 Kph=4 Incline=0
ifit control AA:BB:CC:DD:EE:FF 12345678 start

# Monitor while exercising
ifit monitor AA:BB:CC:DD:EE:FF 12345678

# Stop when done
ifit control AA:BB:CC:DD:EE:FF 12345678 stop
```

### Use with Zwift
```bash
# Start relay server
ifit ftms AA:BB:CC:DD:EE:FF 12345678 --name "My Treadmill"

# In Zwift: Connect to "My Treadmill" as FTMS device
# Leave terminal running while using Zwift
# Ctrl+C to stop when done
```

### Scripting
```bash
# Get current speed in bash
SPEED=$(ifit read AA:BB:CC:DD:EE:FF 12345678 --current --json | jq -r '.CurrentKph')
echo "Speed: $SPEED km/h"

# Automated interval training
ifit control AA:BB:CC:DD:EE:FF 12345678 start
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5
sleep 60
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 8
sleep 60
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5
sleep 60
ifit control AA:BB:CC:DD:EE:FF 12345678 stop
```

## Common Characteristics

| Name | Description | Typical Range |
|------|-------------|---------------|
| Kph | Target speed | 0-25 km/h |
| CurrentKph | Actual speed | 0-25 km/h |
| Incline | Target incline | -3 to 15% |
| CurrentIncline | Actual incline | -3 to 15% |
| Pulse | Heart rate | 0-220 bpm |
| Mode | Running mode | 0=stopped, 1=running |
| MaxKph | Max speed | Equipment limit |
| MinKph | Min speed | Equipment limit |
| MaxIncline | Max incline | Equipment limit |
| MinIncline | Min incline | Equipment limit |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Device not found | Increase `--timeout`, ensure BLE enabled |
| Connection fails | Check address and activation code |
| Permission denied | Run with sudo (Linux) or check BLE permissions |
| Import errors | Run `pip install -e .` in python directory |

## Tips

- Save your device address and code for easy reuse
- Use `--json` flag for scripting and automation
- Monitor in one terminal while controlling from another
- FTMS relay must stay running while using Zwift
- Press Ctrl+C to cleanly stop monitoring or FTMS relay
