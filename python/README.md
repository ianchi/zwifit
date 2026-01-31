# Python modules

This folder contains the Python implementation of Zwifit's BLE tooling.

## Package: `ifit_ble`

- `client.py`: High-level `IFitBleClient` that connects, enables, reads, and
  writes characteristics.
- `protocol.py`: Low-level protocol framing, command constants, bitmaps, and
  characteristic converters.
- `scanner.py`: BLE scan helpers for discovering iFit devices.
- `ftms.py`: FTMS parsing helpers for equipment that speaks the BLE FTMS spec.
- `ftms_server.py`: A local FTMS server that proxies iFit data to FTMS clients.
- `cli.py`: Comprehensive CLI tool for interacting with iFit equipment.

## Installation

```bash
# Install in development mode
pip install -e .

# Or install with dependencies
pip install -e ".[dev]"
```

## CLI Usage

The `ifit` command provides multiple subcommands for interacting with iFit equipment:

### Discover Devices

Find iFit devices using the 4-character BLE code displayed on the equipment:

```bash
ifit discover 1a2b
```

### Discover Activation Code

**Method 1: Automatic Discovery (Try All Codes)**

The easiest way - automatically try all known activation codes until one works:

```python
from ifit_ble import IFitBleClient

client = IFitBleClient("AA:BB:CC:DD:EE:FF")
code, model = await client.try_activation_codes()
print(f"Activated {model} with code: {code}")

# Now use the client normally
values = await client.read_current_values()
```

See [AUTO_ACTIVATION.md](AUTO_ACTIVATION.md) for complete documentation.

**Method 2: BLE Proxy (Intercept from App)**

Capture the activation code by intercepting it from the manufacturer's app:

```bash
ifit discover-activation 1a2b
```

This creates a BLE proxy that captures the 8-character activation code when you connect via your manufacturer's app (iFit, NordicTrack, ProForm, etc.). See [ACTIVATION_DISCOVERY.md](ACTIVATION_DISCOVERY.md) for detailed instructions.

**Requirements:** `pip install bless`

### Equipment Information

Display detailed information about connected equipment:

```bash
ifit info AA:BB:CC:DD:EE:FF 12345678
ifit info AA:BB:CC:DD:EE:FF 12345678 --verbose
```

### List Capabilities

List all supported capabilities and commands:

```bash
ifit capabilities AA:BB:CC:DD:EE:FF 12345678
```

### Read Values

Read characteristic values from the equipment:

```bash
# Read current workout values (Kph, CurrentKph, CurrentIncline, Pulse, Mode)
ifit read AA:BB:CC:DD:EE:FF 12345678 --current

# Read specific characteristics by name
ifit read AA:BB:CC:DD:EE:FF 12345678 Kph Incline Pulse

# Output as JSON
ifit read AA:BB:CC:DD:EE:FF 12345678 --current --json
```

### Write Values

Write characteristic values to control the equipment:

```bash
ifit write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0 Incline=2
```

### Control Commands

Send specific control commands to the treadmill:

```bash
# Start/stop the treadmill
ifit control AA:BB:CC:DD:EE:FF 12345678 start
ifit control AA:BB:CC:DD:EE:FF 12345678 stop

# Set speed (km/h)
ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5.0

# Set incline (%)
ifit control AA:BB:CC:DD:EE:FF 12345678 incline --value 2.5

# Calibrate incline
ifit control AA:BB:CC:DD:EE:FF 12345678 calibrate-incline
```

### Monitor Real-time

Monitor equipment values in real-time:

```bash
ifit monitor AA:BB:CC:DD:EE:FF 12345678
ifit monitor AA:BB:CC:DD:EE:FF 12345678 --interval 0.5
```

### FTMS Relay Server

Run a FTMS BLE relay server to expose iFit equipment to FTMS-compatible apps:

```bash
ifit ftms AA:BB:CC:DD:EE:FF 12345678
ifit ftms AA:BB:CC:DD:EE:FF 12345678 --name "My Treadmill" --interval 1.0
```

## Documentation

- `ifit.md`: iFit BLE protocol summary used by both the JS and Python clients.
