# iFit CLI Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ifit CLI                                 │
│                    (cli.py - Entry Point)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   Discovery  │      │    Client    │     │  FTMS Relay  │
│   Commands   │      │   Commands   │     │   Command    │
└──────────────┘      └──────────────┘     └──────────────┘
        │                     │                     │
        │                     │                     │
    discover            ┌─────┴─────┐            ftms
        │               │           │              │
        │           ┌───┴───┐   ┌───┴───┐          │
        │           │       │   │       │          │
        │         info  capabilities monitor       │
        │           │       │   │       │          │
        │         read   control write  │          │
        │                                          │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   scanner    │      │    client    │     │ ftms_server  │
│  (BLE scan)  │      │  (Protocol)  │     │(FTMS Bridge) │
└──────────────┘      └──────────────┘     └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │   protocol   │
                      │ (Low-level)  │
                      └──────────────┘
                              │
                              ▼
                         BLE Device
                      (iFit Equipment)
```

## Command Categories

### 1. Discovery Commands
**Purpose:** Find and identify iFit devices  
**Commands:**
- `discover` - Scan for devices by BLE code

### 2. Information Commands
**Purpose:** Query device capabilities and status  
**Commands:**
- `info` - Show equipment information
- `capabilities` - List supported capabilities
- `read` - Read characteristic values

### 3. Control Commands
**Purpose:** Interact with and control equipment  
**Commands:**
- `write` - Write characteristic values
- `control` - Send specific control commands (start/stop/speed/incline)

### 4. Monitoring Commands
**Purpose:** Real-time observation  
**Commands:**
- `monitor` - Display live workout metrics

### 5. Relay Commands
**Purpose:** Bridge to other protocols  
**Commands:**
- `ftms` - Run FTMS relay server for Zwift/TrainerRoad/etc.

## Data Flow Example: Speed Change

```
User Command:
  ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5.0

         │
         ▼
    CLI Parser (cli.py)
    - Parse arguments
    - Validate inputs
    - Route to _control_treadmill()
         │
         ▼
    Client (client.py)
    - Connect to device
    - Call write_characteristics({"Kph": 5.0})
         │
         ▼
    Protocol (protocol.py)
    - Build write request
    - Encode value as bytes
    - Frame message
         │
         ▼
    BLE Layer (bleak)
    - Write to TX characteristic
    - Wait for RX notification
         │
         ▼
    iFit Equipment
    - Process command
    - Update motor speed
    - Send confirmation
         │
         ▼
    Response Flow (reverse)
    - RX notification → protocol → client → CLI
    - Display "✓ Speed set to 5.0 km/h"
```

## Module Responsibilities

| Module | Responsibility | Key Functions |
|--------|---------------|---------------|
| `cli.py` | User interface, argument parsing, command routing | `main()`, `_parse_args()`, command handlers |
| `client.py` | High-level BLE client, protocol orchestration | `connect()`, `read_characteristics()`, `write_characteristics()` |
| `scanner.py` | Device discovery via BLE scanning | `find_ifit_device()` |
| `protocol.py` | Message framing, encoding/decoding, checksums | `build_request()`, `parse_*_response()` |
| `ftms_server.py` | FTMS protocol bridge, BLE server | `FtmsBleRelay`, characteristic handlers |
| `ftms.py` | FTMS data encoding/decoding | `encode_treadmill_data()`, `encode_control_point_response()` |

## Extension Points

The CLI is designed for easy extension:

1. **New Commands** - Add to `_parse_args()` and create handler function
2. **New Control Actions** - Extend `_control_treadmill()` with new cases
3. **New Output Formats** - Add format flags (e.g., `--csv`, `--xml`)
4. **New Relay Protocols** - Follow FTMS pattern in separate module

## File Organization

```
python/
├── pyproject.toml           # Package config, entry point
├── requirements.txt         # Direct dependencies
├── README.md               # Full documentation
├── QUICKSTART.md           # User getting started guide
├── CHEATSHEET.md           # Quick command reference
├── CLI_IMPLEMENTATION.md   # This implementation doc
└── ifit_ble/
    ├── __init__.py         # Package exports
    ├── cli.py              # ⭐ Main CLI application
    ├── client.py           # High-level client
    ├── scanner.py          # Device discovery
    ├── protocol.py         # Protocol implementation
    ├── ftms.py             # FTMS codec
    ├── ftms_server.py      # FTMS relay server
    └── ftms_server_cli.py  # (Deprecated - use `ifit ftms`)
```

## Usage Patterns

### Pattern 1: Interactive Use
User types commands directly, sees formatted output
```bash
$ ifit discover 1a2b
Scanning for iFit device with code '1a2b'...

✓ Found device:
  Address: AA:BB:CC:DD:EE:FF
  Name: iFit Treadmill
  Manufacturer Data: 010203...
```

### Pattern 2: Scripting
Use JSON output for parsing in scripts
```bash
#!/bin/bash
DEVICE="AA:BB:CC:DD:EE:FF"
CODE="12345678"

# Get current speed
SPEED=$(ifit read $DEVICE $CODE --current --json | jq -r '.CurrentKph')

if (( $(echo "$SPEED > 10" | bc -l) )); then
    echo "Slowing down..."
    ifit control $DEVICE $CODE speed --value 5
fi
```

### Pattern 3: Server Mode
Run as long-lived process
```bash
# Terminal 1: Run FTMS relay
$ ifit ftms AA:BB:CC:DD:EE:FF 12345678 --name "Treadmill"
Starting FTMS relay server 'Treadmill'...
✓ Server running (Ctrl+C to stop)
[... stays running ...]

# Terminal 2: Open Zwift, connect to "Treadmill"
```

### Pattern 4: Monitoring
Real-time display with periodic updates
```bash
$ ifit monitor AA:BB:CC:DD:EE:FF 12345678 --interval 0.5
Monitoring equipment (Ctrl+C to stop)...

CurrentIncline: 2 | CurrentKph: 5.2 | Kph: 5.0 | Mode: 1 | Pulse: 125
```
