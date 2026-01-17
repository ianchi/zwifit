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
- `ftms_server_cli.py`: CLI wrapper to run the FTMS server.

## Documentation

- `ifit.md`: iFit BLE protocol summary used by both the JS and Python clients.
