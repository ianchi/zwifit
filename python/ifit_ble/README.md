# iFit BLE Client (Bleak)

This package contains a Python 3.11 implementation of the iFit BLE protocol used
by Zwifit. It mirrors the custom request/response framing, capability discovery,
and value reads/writes from the original Node implementation.

## Quick start

### Option 1: Monitor-only mode (NO activation code required)

**New!** Monitor your treadmill without an activation code (read-only):

```python
import asyncio
from ifit_ble import IFitBleClient, find_ifit_device

async def main() -> None:
    device = await find_ifit_device("1a2b")
    
    # No activation code needed for monitoring!
    client = IFitBleClient(device.address, monitor_only=True)
    await client.connect()

    # Read basic state (pace, incline, distance, pulse, timer)
    state = await client.monitor_basic_state()
    print(state)  # {'pace': 5.0, 'incline': 2.5, 'distance': 1000, ...}
    
    # Can also read individual characteristics
    values = await client.read_characteristics(["Kph", "Incline"])
    print(values)
    
    await client.disconnect()

asyncio.run(main())
```

### Option 2: Full control with activation code

For read/write control (requires activation code):

```python
import asyncio
from ifit_ble import IFitBleClient, WriteValue, find_ifit_device

async def main() -> None:
    device = await find_ifit_device("1a2b")
    client = IFitBleClient(device.address, activation_code="deadbeef")
    await client.connect()

    # Read current values
    current = await client.read_current_values()
    print(current)

    # Write AND read
    await client.write_and_read(
        writes=[WriteValue(client.equipment_information.characteristics[0], 6.0)],
        reads=["CurrentKph", "CurrentIncline"],
    )

    await client.disconnect()

asyncio.run(main())
```

### Option 3: Hardcoded sequences (specific models only)

For supported models, bypass activation code entirely:

```python
client = IFitBleClient(device.address, model="proform_treadmill_l6_0s")
```

## Initialization Modes

| Mode | Authentication | Read | Write | Use Case |
|------|----------------|------|-------|----------|
| `monitor_only=True` | None | ✓ | ✗ | Workout logging, no control |
| `model="..."` | None | ✓ | ✓ | Specific supported models |
| `activation_code="..."` | Required | ✓ | ✓ | Full control, any device |

## Notes

- The BLE code is the 4-character hex suffix shown on the treadmill display.
- The activation code must be passed as a hex string (no `0x` prefix).
- Monitor-only mode uses the NongoFit approach for read-only access without authentication.
- The protocol logic lives in `protocol.py`, including checksums, bitmaps, and
  characteristic conversions.
