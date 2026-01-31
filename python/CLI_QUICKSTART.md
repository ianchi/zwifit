# iFit BLE CLI Quick Start

## Installation

```bash
cd python
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# or: source venv/bin/activate  # Linux/Mac
pip install -e .
```

## Quick Commands

### 1. Monitor WITHOUT Activation Code (NEW! ⭐)

**This is the easiest way to get started - no activation code needed!**

```bash
# First, find your device
python -m ifit_ble.cli list

# Then monitor it (read-only, no control)
python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF

# With custom update interval
python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF --interval 0.5
```

Output shows:
- Pace (kph)
- Incline (%)
- Distance
- Pulse (bpm)
- Timer (seconds)

### 2. Discover Devices

```bash
# List all iFit devices in range
python -m ifit_ble.cli list

# Find device by BLE code (4 digits shown on treadmill)
python -m ifit_ble.cli discover 1a2b
```

### 3. Full Control (Requires Activation Code)

```bash
# Show equipment info
python -m ifit_ble.cli info AA:BB:CC:DD:EE:FF 12345678

# Read current values
python -m ifit_ble.cli read AA:BB:CC:DD:EE:FF 12345678 --current

# Read specific characteristics
python -m ifit_ble.cli read AA:BB:CC:DD:EE:FF 12345678 Kph Incline

# Write values
python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0 Incline=2

# Monitor with full details
python -m ifit_ble.cli monitor AA:BB:CC:DD:EE:FF 12345678
```

### 4. Hardcoded Model Support

For supported models, no activation code needed:

```bash
# List supported models
python -m ifit_ble.cli list-models

# Connect using model
python -m ifit_ble.cli connect AA:BB:CC:DD:EE:FF --model proform_treadmill_l6_0s
```

## Command Reference

### Discovery Commands

| Command | Description | Example |
|---------|-------------|---------|
| `list` | List all iFit devices | `python -m ifit_ble.cli list` |
| `discover <code>` | Find device by BLE code | `python -m ifit_ble.cli discover 1a2b` |
| `list-models` | Show supported models | `python -m ifit_ble.cli list-models` |

### Monitoring Commands

| Command | Auth? | Description | Example |
|---------|-------|-------------|---------|
| `monitor-only <addr>` | ❌ No | Read-only monitoring | `python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF` |
| `monitor <addr> <code>` | ✅ Yes | Full monitoring | `python -m ifit_ble.cli monitor AA:BB:CC:DD:EE:FF 12345678` |

### Control Commands (Require Activation Code)

| Command | Description | Example |
|---------|-------------|---------|
| `info <addr> <code>` | Show equipment info | `python -m ifit_ble.cli info AA:BB:CC:DD:EE:FF 12345678` |
| `read <addr> <code> <chars>` | Read characteristics | `python -m ifit_ble.cli read AA:BB:CC:DD:EE:FF 12345678 Kph` |
| `write <addr> <code> <vals>` | Write characteristics | `python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0` |
| `control <addr> <code> <act>` | Control treadmill | `python -m ifit_ble.cli control AA:BB:CC:DD:EE:FF 12345678 start` |
| `capabilities <addr> <code>` | List capabilities | `python -m ifit_ble.cli capabilities AA:BB:CC:DD:EE:FF 12345678` |

## Typical Workflow

### For Monitoring Only (No Code)

```bash
# Step 1: Find your treadmill
python -m ifit_ble.cli list

# Step 2: Start monitoring (copy the address from step 1)
python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF

# Done! Press Ctrl+C to stop
```

### For Full Control (With Code)

```bash
# Step 1: Find your treadmill
python -m ifit_ble.cli discover 1a2b

# Step 2: Get device info
python -m ifit_ble.cli info AA:BB:CC:DD:EE:FF 12345678

# Step 3: Control it
python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0

# Or monitor it
python -m ifit_ble.cli monitor AA:BB:CC:DD:EE:FF 12345678
```

## Common Options

- `--interval <seconds>` - Update interval for monitoring (default: 1.0)
- `--timeout <seconds>` - Scan timeout (default: 10.0)
- `--verbose` / `-v` - Show detailed information
- `--json` - Output as JSON (for read commands)

## Examples

### Quick Workout Monitoring

```bash
# Simple monitoring
python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF
```

Output:
```
  Time | Pace (kph) | Incline (%) |   Distance | Pulse (bpm) |  Timer (s)
--------------------------------------------------------------------------------
     0 |        5.0 |         2.5 |       1000 |         120 |        300
     1 |        5.2 |         2.5 |       1015 |         122 |        301
     2 |        5.5 |         3.0 |       1030 |         125 |        302
```

### Find and Connect

```bash
# Scan for devices
python -m ifit_ble.cli list --timeout 15

# Monitor the first one found
python -m ifit_ble.cli monitor-only AA:BB:CC:DD:EE:FF
```

### Speed Control

```bash
# Set speed to 5 km/h
python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0

# Set incline to 2%
python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Incline=2.0

# Set both
python -m ifit_ble.cli write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0 Incline=2.0
```

## Troubleshooting

### "No module named 'bleak'"
```bash
pip install -e .
```

### "No iFit devices found"
- Make sure treadmill is on
- Check Bluetooth is enabled
- Move closer to the device
- Increase timeout: `--timeout 20`

### "Connection failed"
- Verify correct MAC address
- Make sure treadmill is not connected to another device
- Check activation code is correct (if using full control)

### "Cannot control treadmill"
- Use `monitor-only` for read-only without activation code
- Or get proper activation code for write access
- Or use hardcoded model if supported

## Notes

- **Monitor-only mode** uses the NongoFit approach - no authentication needed
- **Activation codes** are 8-character hex strings (no "0x" prefix)
- **BLE codes** are 4-character hex shown on treadmill display
- **MAC addresses** are in format `AA:BB:CC:DD:EE:FF`
