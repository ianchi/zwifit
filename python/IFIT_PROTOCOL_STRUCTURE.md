# iFit BLE Protocol Structure

This document provides a comprehensive explanation of the iFit BLE protocol structure used for communicating with iFit-enabled fitness equipment (treadmills, bikes, ellipticals, etc.) over Bluetooth Low Energy.

## Table of Contents

- [Overview](#overview)
- [BLE Connection](#ble-connection)
- [Protocol Layers](#protocol-layers)
- [Message Structure](#message-structure)
- [Commands](#commands)
- [Characteristics](#characteristics)
- [Data Types and Converters](#data-types-and-converters)
- [Request/Response Flow](#requestresponse-flow)
- [Examples](#examples)

---

## Overview

The iFit BLE protocol is a proprietary protocol used by iFit-enabled fitness equipment to:
- Control equipment parameters (speed, incline, resistance, etc.)
- Monitor equipment state (current values, mode, workout stats)
- Discover equipment capabilities
- Authenticate and unlock equipment for control

The protocol uses a custom framing scheme over standard BLE GATT characteristics, with messages split into chunks to fit BLE's 20-byte MTU limitation.

---

## BLE Connection

### Service and Characteristics

The iFit protocol uses a custom BLE service with two characteristics:

```python
BLE_UUIDS = {
    "service": "000015331412efde1523785feabcd123",  # iFit service
    "rx": "000015351412efde1523785feabcd123",       # Device receives (client writes)
    "tx": "000015341412efde1523785feabcd123",       # Device transmits (client reads/notifies)
}
```

- **Service UUID**: The main iFit service identifier
- **RX Characteristic**: Used to send commands TO the equipment (client writes)
- **TX Characteristic**: Used to receive responses FROM the equipment (client subscribes to notifications)

### Connection Flow

1. **Scan** for BLE devices advertising the iFit service UUID
2. **Connect** to the device
3. **Discover services** (may need to wait for device reconfiguration)
4. **Subscribe** to TX characteristic notifications
5. **Authenticate** using activation code (for control) or skip (for monitoring)
6. **Discover** equipment capabilities
7. **Send commands** and receive responses

---

## Protocol Layers

The iFit protocol has three distinct layers:

```
┌─────────────────────────────────┐
│   BLE Framing Layer             │  ← Splits messages into 20-byte chunks
├─────────────────────────────────┤
│   Command Protocol Layer        │  ← Encodes commands, checksums, equipment ID
├─────────────────────────────────┤
│   Data Encoding Layer           │  ← Characteristic values, bitmaps, converters
└─────────────────────────────────┘
```

---

## Message Structure

### Layer 1: BLE Framing

BLE has a 20-byte MTU (Maximum Transmission Unit), but the first 2 bytes are used for framing metadata, leaving 18 bytes for payload data per chunk.

#### Header Chunk

The first chunk of every request/response:

```
┌────┬────┬────┬────┐
│ FE │ 02 │ LL │ NN │
└────┴────┴────┴────┘
  0    1    2    3

FE = Message header marker (0xFE = MessageIndex.HEADER)
02 = Fixed value
LL = Total length of the raw request/response (before chunking)
NN = Total number of chunks (including this header chunk)
```

#### Payload Chunks

Subsequent chunks contain actual data:

```
┌────┬────┬──────────────────────┐
│ TT │ LL │ <payload bytes>      │
└────┴────┴──────────────────────┘
  0    1    2-19 (up to 18 bytes)

TT = Chunk index (0, 1, 2...) or 0xFF (MessageIndex.EOF) for final chunk
LL = Number of payload bytes in this chunk (max 18)
```

**Example**: A 40-byte request is split into:
- 1 header chunk (4 bytes)
- 2 payload chunks (18 bytes each)
- 1 final chunk (4 bytes, marked with 0xFF)

### Layer 2: Command Protocol

The raw command payload (before chunking):

```
┌────┬────┬────┬────┬────┬────┬────┬──────────┬────┐
│ 02 │ 04 │ 02 │ LL │ EE │ LL │ CC │ PAYLOAD  │ SS │
└────┴────┴────┴────┴────┴────┴────┴──────────┴────┘
  0    1    2    3    4    5    6    7...      -1

Bytes 0-2: Fixed prefix (0x02, 0x04, 0x02) - iFit protocol signature
Byte 3:    LL = Payload length + 4
Byte 4:    EE = Equipment identifier (SportsEquipment enum)
Byte 5:    LL = Payload length + 4 (repeated)
Byte 6:    CC = Command identifier (Command enum)
Bytes 7+:  Command-specific payload
Last byte: SS = Checksum (low byte of sum of EE + LL + CC + all payload bytes)
```

#### Equipment Identifiers

```python
class SportsEquipment(IntEnum):
    GENERAL = 2      # Generic equipment
    TREADMILL = 4    # Treadmill-specific
```

#### Command Identifiers

```python
class Command(IntEnum):
    WRITE_AND_READ = 2              # 0x02 Set/get characteristic values (most common)
    CALIBRATE = 6                   # 0x06 Calibrate sensors (e.g., incline)
    SUPPORTED_CAPABILITIES = 128    # 0x80 Query supported features
    EQUIPMENT_INFORMATION = 129     # 0x81 Get equipment metadata
    EQUIPMENT_REFERENCE = 130       # 0x82 Get reference number
    EQUIPMENT_FIRMWARE = 132        # 0x84 Get firmware version
    SUPPORTED_COMMANDS = 136        # 0x88 Query supported commands
    ENABLE = 144                    # 0x90 Authenticate/unlock equipment
    EQUIPMENT_SERIAL = 149          # 0x95 Get serial number
```

Init sequence: 81 - 80 - 88 - 82 - 84 - 95 - 90

### Layer 3: Data Encoding

The command payload contains:
- **Bitmaps**: Indicate which characteristics are being written/read
- **Values**: Encoded characteristic values in ascending ID order
- **Metadata**: Command-specific data

---

## Commands

### ENABLE (0x90) - Authentication

Unlocks equipment for control using an activation code.

**Payload**:
```
┌──────────────────┐
│ 43-byte code     │  Activation code (hex string converted to bytes)
└──────────────────┘
```

**Example**:
```python
activation_code = "0102030405060708"
payload = bytes.fromhex(activation_code)
request = build_request(SportsEquipment.TREADMILL, Command.ENABLE, payload)
```

### EQUIPMENT_INFORMATION (0x81) - Discover Characteristics

Queries which characteristics the equipment supports.

**Payload**: None

**Response** (starting at byte 16):
```
┌────┬──────────────────────┐
│ LL │ bitmap bytes         │
└────┴──────────────────────┘

LL = Number of bitmap bytes
Bitmap: Each bit represents a characteristic ID (bit 0 = ID 0, bit 1 = ID 1, etc.)
```

**Example characteristics bitmap**:
```
Byte 0 (bits 0-7):   IDs 0-7   (Kph, Incline, ..., Unknown)
Byte 1 (bits 0-7):   IDs 8-15  (Unknown, Volume, Pulse, UpTime, Mode, ...)
...
```

### EQUIPMENT_REFERENCE (0x82) - Get Reference Number

Retrieves the device reference number.

**Payload**: `00 00`

**Response Structure**:
```
┌────┬────┬────┬────┬────┬────┬────┬────┬────┬──────┬────────────────┬───────────┐
│ 01 │ 04 │ 02 │ LL │ 04 │ LL │ FLAGS.. │ ... │ REF (LE 4-byte) │ ...       │
└────┴────┴────┴────┴────┴────┴─────────┴─────┴────────────────┴───────────┘
  0    1    2    3    4    5    6-7      ...   15-18             19+

Byte 0-1:   Header (0104)
Byte 2:     Sub-command (02)
Byte 3:     Length indicator
Byte 4:     Device type (04 or 07)
Byte 5:     Length repeated
Byte 6-14:  Metadata/flags
Byte 15-18: Reference number (little-endian 4-byte integer)
Byte 19+:   Additional data
```

**Example**:
- Input: `01040221042182026400014d2409002cfe0500780036e8030024f400f40101000102000061`
- Reference at bytes 15-18: `2cfe0500` = 392748 (decimal)

### EQUIPMENT_FIRMWARE (0x84) - Get Firmware Version

Retrieves the firmware version string.

**Payload**: `00 00`

**Response Structure**:
```
┌────┬────┬────┬────┬────┬────┬──────┬──────┬────┬─────────────────┐
│ 01 │ 04 │ 02 │ LL │ 04 │ LL │ FLAGS... │ ?? │ ASCII String... │
└────┴────┴────┴────┴────┴────┴──────────┴────┴─────────────────┘
  0    1    2    3    4    5    6-10      11+   Firmware version

Byte 0-1:   Header (0104)
Byte 2:     Sub-command (02)
Byte 3:     Length indicator
Byte 4:     Device type (04 or 07)
Byte 5-10:  Metadata/flags
Byte 11+:   ASCII firmware version string (terminated by control char \x01 or \x00)
```

**Example**:
- Input: `0104021c041c840250a300302e312e30363132323031372e30393038012a0316`
- Firmware from byte 11: `0.1.06122017.0908`

### EQUIPMENT_SERIAL (0x95) - Get Serial Number

Retrieves the device serial number.

**Payload**: `00 00`

**Response Structure**:
```
┌────┬────┬────┬────┬────┬────┬──────┬────┬────┬────────────────────┬────┐
│ 01 │ 04 │ 02 │ LL │ 04 │ ?? │ FLAGS │ ?? │ LN │ ASCII Serial...    │ CS │
└────┴────┴────┴────┴────┴────┴───────┴────┴────┴────────────────────┴────┘
  0    1    2    3    4    5    6-7     8    9    10+                 -1

Byte 0-1:   Header (0104)
Byte 2:     Sub-command (02)
Byte 3:     Length indicator
Byte 4:     Device type (04 or 07)
Byte 5-7:   Metadata/flags
Byte 8:     Serial string length (LN, e.g., 0x12 = 18 chars)
Byte 9+:    ASCII serial number string (LN bytes)
Last byte:  Checksum

Serial Format: ######-MODEL### (e.g., 392747-MM74Y102555)
```

**Example**:
- Input: `0104021804189502123339323734372d4d4d373459313032353535c2`
- Byte 8: `0x12` = 18 (length)
- Serial from bytes 9-26: `392747-MM74Y102555` (18 chars)
- Checksum: `c2`

### SUPPORTED_CAPABILITIES (0x80) - Discover Features

Queries high-level capabilities (Speed, Incline, Pulse, etc.).

**Payload**: None

**Response** (starting at byte 8):
```
┌────┬──────────────────┐
│ NN │ capability IDs   │
└────┴──────────────────┘

NN = Number of capabilities
Each subsequent byte is a capability ID
```

**Example capabilities**:
```python
CAPABILITIES = {
    "Speed": CapabilityDefinition(65, 0),     # ID 65, characteristic 0
    "Incline": CapabilityDefinition(66, 1),   # ID 66, characteristic 1
    "Pulse": CapabilityDefinition(70, 10),    # ID 70, characteristic 10
    "Key": CapabilityDefinition(71, 7),       # ID 71, characteristic 7
    "Distance": CapabilityDefinition(77, 6),  # ID 77, characteristic 6
    "Time": CapabilityDefinition(78, 11),     # ID 78, characteristic 11
}
```

### WRITE_AND_READ (0x02) - Control and Monitor

The most common command - simultaneously sets values (write) and retrieves values (read).

**Payload Structure**:
```
┌─────────────┬────────────┬────────────────┐
│ Write bitmap│ Read bitmap│ Write values   │
└─────────────┴────────────┴────────────────┘
```

#### Bitmap Structure

Each bitmap encodes which characteristics are included:

```
┌────┬──────────────────────┐
│ LL │ bitmap bytes         │
└────┴──────────────────────┘

LL = Number of bitmap bytes that follow
Each bit indicates if that characteristic ID is included
```

**Example**: Request characteristics 0, 1, 4, 10
```
Characteristic IDs: 0, 1, 4, 10

Byte 0 (IDs 0-7):   0b00010011 = 0x13  (bits 0, 1, 4 set)
Byte 1 (IDs 8-15):  0b00000100 = 0x04  (bit 2 = ID 10 set)

Bitmap: [0x02, 0x13, 0x04]
        ^^^^  ^^^^  ^^^^
         LL   Byte0 Byte1
```

#### Write Values Encoding

After the read bitmap, write values are appended **in ascending characteristic ID order**, using each characteristic's converter.

**Example**: Write Kph=5.5 (ID 0) and Incline=3.0 (ID 1)
```
Kph (ID 0):     5.5 → 550 (×100) → [0x26, 0x02] (little-endian uint16)
Incline (ID 1): 3.0 → 300 (×100) → [0x2C, 0x01] (little-endian uint16)

Write values: [0x26, 0x02, 0x2C, 0x01]
```

#### Read Values Response

Response contains read values **in ascending characteristic ID order**, starting at byte 8.

**Example response**:
```
Bytes 0-7:  Protocol header
Bytes 8-9:  Kph value (2 bytes)
Bytes 10-11: Incline value (2 bytes)
Bytes 12-15: CurrentDistance value (4 bytes)
Bytes 16-19: Pulse value (4 bytes)
...
Last byte:  Checksum
```

---

## Characteristics

Characteristics represent equipment parameters and state. Each has:
- **ID**: Unique numeric identifier (0-255)
- **Name**: Human-readable name
- **Read-only**: Whether it can be written
- **Converter**: Data type and encoding/decoding functions

### Common Characteristics

```python
CHARACTERISTICS = {
    # Control characteristics (writable)
    "Kph": CharacteristicDefinition(0, False, double),        # Target speed
    "Incline": CharacteristicDefinition(1, False, double),    # Target incline
    "Volume": CharacteristicDefinition(9, False, uint8),      # Audio volume
    "Mode": CharacteristicDefinition(12, False, mode),        # Equipment mode
    "Metric": CharacteristicDefinition(36, False, boolean),   # Metric units
    
    # Read-only characteristics (status/sensors)
    "CurrentKph": CharacteristicDefinition(16, True, double),       # Actual speed
    "CurrentIncline": CharacteristicDefinition(17, True, double),   # Actual incline
    "CurrentDistance": CharacteristicDefinition(4, True, uint32),   # Distance traveled
    "CurrentTime": CharacteristicDefinition(20, True, uint32),      # Workout duration (seconds)
    "CurrentCalories": CharacteristicDefinition(21, True, calories), # Calories burned
    "Pulse": CharacteristicDefinition(10, False, pulse),            # Heart rate data
    "Distance": CharacteristicDefinition(6, True, uint32),          # Total distance
    "UpTime": CharacteristicDefinition(11, True, uint32),           # Equipment uptime
    "Calories": CharacteristicDefinition(13, True, calories),       # Total calories
    
    # Equipment limits
    "MaxIncline": CharacteristicDefinition(27, True, double),
    "MinIncline": CharacteristicDefinition(28, True, double),
    "MaxKph": CharacteristicDefinition(30, True, double),
    "MinKph": CharacteristicDefinition(31, True, double),
    "MaxPulse": CharacteristicDefinition(49, True, uint8),
    
    # Summary/statistics
    "AverageIncline": CharacteristicDefinition(52, True, double),
    "TotalTime": CharacteristicDefinition(70, True, uint32),
    "PausedTime": CharacteristicDefinition(103, True, uint32),
}
```

### Equipment Modes

```python
class Mode(IntEnum):
    UNKNOWN = 0              # Unknown state
    IDLE = 1                 # Equipment is idle/ready
    ACTIVE = 2               # Workout in progress
    PAUSE = 3                # Workout paused
    SUMMARY = 4              # Showing workout summary
    SETTINGS = 7             # In settings menu
    MISSING_SAFETY_KEY = 8   # Safety key not inserted
```

---

## Data Types and Converters

Each characteristic uses a converter to encode/decode values.

### Converter Structure

```python
@dataclass(frozen=True)
class Converter:
    size: int                                    # Size in bytes
    from_buffer: Callable[[bytes, int], Any]    # Decode from bytes
    to_buffer: Callable[[bytearray, int, Any], int]  # Encode to bytes
```

### Built-in Converters

#### double (2 bytes)
Scaled uint16 with 2 decimal places (×100).

```python
# Encode: 5.5 → 550 → [0x26, 0x02] (little-endian)
# Decode: [0x26, 0x02] → 550 → 5.5
```

#### uint8 (1 byte)
Unsigned 8-bit integer (0-255).

```python
# Encode: 10 → [0x0A]
# Decode: [0x0A] → 10
```

#### uint16 (2 bytes)
Unsigned 16-bit integer, little-endian.

```python
# Encode: 1000 → [0xE8, 0x03]
# Decode: [0xE8, 0x03] → 1000
```

#### uint32 (4 bytes)
Unsigned 32-bit integer, little-endian.

```python
# Encode: 123456 → [0x40, 0xE2, 0x01, 0x00]
# Decode: [0x40, 0xE2, 0x01, 0x00] → 123456
```

#### boolean (1 byte)
Boolean flag (0 or 1).

```python
# Encode: True → [0x01], False → [0x00]
# Decode: [0x01] → True, [0x00] → False
```

#### calories (4 bytes)
Special iFit scaling for calories (×1024 / 100000000).

```python
# Encode: 100.0 cal → 9765625 → [0x89, 0x0F, 0x95, 0x00]
# Decode: [0x89, 0x0F, 0x95, 0x00] → 9765625 → 100.0 cal
```

#### pulse (4 bytes)
Composite pulse data structure.

```python
# Structure:
# Byte 0: Current pulse (BPM)
# Byte 1: Average pulse (BPM)
# Byte 2: Pulse count
# Byte 3: Pulse source (PulseSource enum)

# Encode: {"pulse": 120, "source": PulseSource.BLE} 
#      → [0x78, 0x00, 0x00, 0x04]

# Decode: [0x78, 0x50, 0x0A, 0x04]
#      → {"pulse": 120, "average": 80, "count": 10, "source": PulseSource.BLE}
```

#### Pulse Sources

```python
class PulseSource(IntEnum):
    NO = 0         # No heart rate
    HAND = 1       # Hand grip sensors
    UNKNOWN = 2    # Unknown source
    UNKNOWN2 = 3   # Unknown source
    BLE = 4        # Bluetooth heart rate monitor
```

---

## Request/Response Flow

### 1. Equipment Discovery

```python
# Send: EQUIPMENT_INFORMATION command
request = build_request(SportsEquipment.TREADMILL, Command.EQUIPMENT_INFORMATION)

# Response: Bitmap of supported characteristics
characteristics = parse_equipment_information_response(response)
# Returns: {0: Kph, 1: Incline, 4: CurrentDistance, ...}
```

### 2. Capability Discovery

```python
# Send: SUPPORTED_CAPABILITIES command
request = build_request(SportsEquipment.TREADMILL, Command.SUPPORTED_CAPABILITIES)

# Response: List of capability IDs
capabilities = parse_features_response(response)
# Returns: [65, 66, 70, 77, 78] (Speed, Incline, Pulse, Distance, Time)
```

### 3. Control Equipment

```python
# Write Kph=5.5 and Incline=3.0, read current values
writes = [
    WriteValue(CHARACTERISTICS["Kph"], 5.5),
    WriteValue(CHARACTERISTICS["Incline"], 3.0),
]
reads = [
    CHARACTERISTICS["CurrentKph"],
    CHARACTERISTICS["CurrentIncline"],
    CHARACTERISTICS["CurrentDistance"],
]

# Build payload
write_bitmap = get_bitmap(equipment_info, writes)
read_bitmap = get_bitmap(equipment_info, reads)
write_values = get_write_values(writes)
payload = write_bitmap + read_bitmap + write_values

# Send command
request = build_request(SportsEquipment.TREADMILL, Command.WRITE_AND_READ, payload)

# Parse response
values = parse_write_and_read_response(equipment_info, response, reads)
# Returns: {"CurrentKph": 5.3, "CurrentIncline": 2.9, "CurrentDistance": 1234}
```

### 4. Monitor-Only Mode

For read-only monitoring without authentication:

```python
# No ENABLE command needed
# Only send WRITE_AND_READ with empty write bitmap
writes = []
reads = [
    CHARACTERISTICS["CurrentKph"],
    CHARACTERISTICS["CurrentIncline"],
    CHARACTERISTICS["Pulse"],
    CHARACTERISTICS["CurrentDistance"],
    CHARACTERISTICS["CurrentTime"],
]

# Build and send request (same as above but no writes)
```

---

## Examples

### Example 1: Set Speed to 10 km/h

```python
# 1. Build write value
write = WriteValue(CHARACTERISTICS["Kph"], 10.0)

# 2. Build bitmaps
write_bitmap = get_bitmap(equipment_info, [write])
# Result: [0x01, 0x01]  (1 byte, bit 0 set for characteristic ID 0)

read_bitmap = get_bitmap(equipment_info, [])
# Result: [0x00]  (no reads)

# 3. Encode value
write_values = get_write_values([write])
# 10.0 → 1000 → [0xE8, 0x03]

# 4. Build payload
payload = write_bitmap + read_bitmap + write_values
# Result: [0x01, 0x01, 0x00, 0xE8, 0x03]

# 5. Build request
request = build_request(SportsEquipment.TREADMILL, Command.WRITE_AND_READ, payload)
# Result: [0x02, 0x04, 0x02, 0x09, 0x04, 0x09, 0x02, 
#          0x01, 0x01, 0x00, 0xE8, 0x03, 0x05]
#          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ header
#                                          ^^^^^ payload
#                                                ^^^^ checksum

# 6. Split into BLE chunks
messages = build_write_messages(request)
# Message 0 (header): [0xFE, 0x02, 0x0D, 0x01]
# Message 1 (payload): [0xFF, 0x0D, 0x02, 0x04, 0x02, 0x09, 0x04, 
#                       0x09, 0x02, 0x01, 0x01, 0x00, 0xE8, 0x03, 0x05]
```

### Example 2: Monitor Current State

```python
# Read 5 characteristics: Kph, Incline, Distance, Time, Pulse
reads = [
    CHARACTERISTICS["CurrentKph"],      # ID 16
    CHARACTERISTICS["CurrentIncline"],  # ID 17
    CHARACTERISTICS["CurrentDistance"], # ID 4
    CHARACTERISTICS["CurrentTime"],     # ID 20
    CHARACTERISTICS["Pulse"],           # ID 10
]

# Build bitmaps
write_bitmap = [0x00]  # No writes
read_bitmap = get_bitmap(equipment_info, reads)
# IDs: 4, 10, 16, 17, 20
# Byte 0 (IDs 0-7):   bit 4 = 0b00010000 = 0x10
# Byte 1 (IDs 8-15):  bit 2 = 0b00000100 = 0x04  (ID 10)
# Byte 2 (IDs 16-23): bits 0,1,4 = 0b00010011 = 0x13  (IDs 16, 17, 20)
# Result: [0x03, 0x10, 0x04, 0x13]

# Build and send request
payload = write_bitmap + read_bitmap
request = build_request(SportsEquipment.TREADMILL, Command.WRITE_AND_READ, payload)

# Parse response (values in ascending ID order: 4, 10, 16, 17, 20)
# Response bytes 8+:
# [0x40, 0xE2, 0x01, 0x00,  ← CurrentDistance (ID 4, 4 bytes) = 123456
#  0x78, 0x50, 0x0A, 0x04,  ← Pulse (ID 10, 4 bytes) = {pulse:120, avg:80, count:10, source:BLE}
#  0x2C, 0x01,              ← CurrentKph (ID 16, 2 bytes) = 3.0
#  0x58, 0x02,              ← CurrentIncline (ID 17, 2 bytes) = 6.0
#  0x78, 0x00, 0x00, 0x00]  ← CurrentTime (ID 20, 4 bytes) = 120 seconds

values = parse_write_and_read_response(equipment_info, response, reads)
# Returns: {
#   "CurrentDistance": 123456,
#   "Pulse": {"pulse": 120, "average": 80, "count": 10, "source": PulseSource.BLE},
#   "CurrentKph": 3.0,
#   "CurrentIncline": 6.0,
#   "CurrentTime": 120
# }
```

### Example 3: Complete Workflow

```python
from ifit_ble import IFitBleClient

# 1. Create client
client = IFitBleClient(
    address="AA:BB:CC:DD:EE:FF",
    activation_code="0102030405060708"
)

# 2. Connect
await client.connect()

# 3. Authenticate
await client.enable()

# 4. Discover equipment info
await client.equipment_information()
# Now client.equipment_information contains supported characteristics

# 5. Set speed and incline
await client.write_and_read(
    writes=[
        WriteValue(CHARACTERISTICS["Kph"], 8.0),
        WriteValue(CHARACTERISTICS["Incline"], 2.0),
    ],
    reads=[]
)

# 6. Monitor state
values = await client.write_and_read(
    writes=[],
    reads=[
        CHARACTERISTICS["CurrentKph"],
        CHARACTERISTICS["CurrentIncline"],
        CHARACTERISTICS["Pulse"],
        CHARACTERISTICS["CurrentDistance"],
        CHARACTERISTICS["CurrentTime"],
    ]
)
print(f"Speed: {values['CurrentKph']} km/h")
print(f"Incline: {values['CurrentIncline']}%")
print(f"Heart Rate: {values['Pulse']['pulse']} BPM")
print(f"Distance: {values['CurrentDistance']} m")
print(f"Time: {values['CurrentTime']} sec")

# 7. Disconnect
await client.disconnect()
```

---

## Implementation References

### Python Implementation
- **Protocol**: [python/ifit_ble/protocol.py](python/ifit_ble/protocol.py)
- **Client**: [python/ifit_ble/client.py](python/ifit_ble/client.py)
- **CLI**: [python/ifit_ble/cli.py](python/ifit_ble/cli.py)

### JavaScript Implementation
- **Protocol**: [src/ble/ifit/](src/ble/ifit/)
- **Constants**: [src/ble/ifit/_constants.js](src/ble/ifit/_constants.js)
- **Request Builder**: [src/ble/ifit/_request.js](src/ble/ifit/_request.js)

### Documentation
- **Overview**: [python/ifit.md](python/ifit.md)
- **Protocol Comparison**: [python/PROTOCOL_COMPARISON.md](python/PROTOCOL_COMPARISON.md)
- **Architecture**: [python/ARCHITECTURE.md](python/ARCHITECTURE.md)
- **Quickstart**: [python/QUICKSTART.md](python/QUICKSTART.md)

---

## Hardcoded Sequences and MTU Compliance

### Known Issues with Third-Party Captures

Some reverse-engineered initialization sequences (e.g., from qdomyos-zwift) contain **non-compliant BLE messages** that exceed the standard 20-byte MTU:

**Example issue**:
```python
# These messages exceed 20 bytes!
bytes.fromhex("001202040202280428900766d40ad0c82c9020a240ea70")  # 23 bytes
bytes.fromhex("01128e16343c4c6476a086a8b2d0d0d2ee0422443c5068")   # 22 bytes
```

**Problems**:
- Message lengths don't match declared lengths in the length byte
- Extra padding bytes at the end corrupt checksums
- Total reconstructed payload exceeds header-declared size

**Likely causes**:
1. Captures include BLE transmission overhead/padding
2. Some devices negotiate larger MTU (up to 251 bytes in BLE 4.2+)
3. Incorrect parsing of BLE sniffer logs

**Recommendation**: Extract the activation code from these sequences and use the clean protocol implementation instead:

```python
# Instead of using hardcoded sequences:
client = IFitBleClient(address, model="proform_treadmill_l6_0s")

# Extract and use the activation code directly:
activation_code = "0766D40AD0C82C90"  # Extracted from sequence
client = IFitBleClient(address, activation_code=activation_code)
```

This ensures proper 20-byte MTU compliance and correct checksums.

---

## Summary

The iFit BLE protocol is a three-layer system:

1. **BLE Framing**: Splits messages into 20-byte chunks with header/index bytes
2. **Command Protocol**: Wraps commands with equipment ID, command ID, and checksum
3. **Data Encoding**: Uses bitmaps to specify characteristics and converters to encode values

Key concepts:
- **Characteristics**: Equipment parameters with unique IDs and data types
- **Commands**: Operations like ENABLE, EQUIPMENT_INFORMATION, WRITE_AND_READ
- **Bitmaps**: Efficient encoding of which characteristics are included in a request
- **Converters**: Type-specific encoding/decoding (double, uint32, calories, pulse, etc.)
- **Checksums**: Simple sum-based validation of request/response integrity

This protocol enables both **control** (writing values) and **monitoring** (reading values) of iFit equipment over BLE, with authentication for control access.
