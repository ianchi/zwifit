# iFit BLE Client (Bleak)

This package contains a Python 3.11 implementation of the iFit BLE protocol used
by Zwifit. It mirrors the custom request/response framing, capability discovery,
and value reads/writes from the original Node implementation.

## Quick start

```python
import asyncio

from ifit_ble import IFitBleClient, WriteValue, find_ifit_device


async def main() -> None:
    device = await find_ifit_device("1a2b")
    client = IFitBleClient(device.address, activation_code="deadbeef")
    await client.connect()

    current = await client.read_current_values()
    print(current)

    await client.write_and_read(
        writes=[WriteValue(client.equipment_information.characteristics[0], 6.0)],
        reads=["CurrentKph", "CurrentIncline"],
    )

    await client.disconnect()


asyncio.run(main())
```

## Notes

- The BLE code is the 4-character hex suffix shown on the treadmill display.
- The activation code must be passed as a hex string (no `0x` prefix).
- The protocol logic lives in `protocol.py`, including checksums, bitmaps, and
  characteristic conversions.
