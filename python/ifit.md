# iFit BLE Protocol Overview

This document summarizes the iFit BLE protocol framing used by Zwifit.
It mirrors the JavaScript implementation in `src/ble/ifit` and the Python
implementation in `python/ifit_ble`.

## BLE UUIDs

- Service UUID: `000015331412efde1523785feabcd123`
- RX characteristic: `000015351412efde1523785feabcd123`
- TX characteristic: `000015341412efde1523785feabcd123`

## Message framing

Each request is wrapped in a BLE message header and split into 20-byte chunks.
The payload chunk size is 18 bytes because the first 2 bytes are metadata.

### Request header chunk

```
TT -- LL NN
```

- `TT` is `0xFE` (header marker).
- `--` is a fixed value `0x02`.
- `LL` is the length of the raw request bytes.
- `NN` is the number of payload chunks plus the header chunk.

### Payload chunks

```
TT LL <payload bytes>
```

- `TT` is the chunk index, or `0xFF` for the final chunk.
- `LL` is the number of payload bytes in this chunk.

## Raw request format

```
02 04 02 LL EE LL CC <payload> SS
```

- `LL` is the payload length plus 4.
- `EE` is the equipment identifier (sports equipment or capability id).
- `CC` is the command id.
- `SS` is a checksum: `EE + LL + CC + sum(payload)` (lowest byte).

## Commands

- `0x02` Write and read values.
- `0x06` Calibrate (used for incline calibration).
- `0x80` Supported capabilities.
- `0x81` Equipment information.
- `0x82` Equipment information (extended).
- `0x84` Equipment information (extended).
- `0x88` Supported commands.
- `0x90` Enable / unlock equipment.
- `0x95` Equipment information (extended).

## Bitmaps and value ordering

Write-and-read requests contain two bitmaps:

1. A bitmap of characteristic ids being written.
2. A bitmap of characteristic ids being read.

The first byte in each bitmap is the number of bytes that follow. Each bit maps
an id in ascending order. Values for write operations are appended in ascending
characteristic id order.

## Checksums

Responses include a trailing checksum. Compute the checksum by summing bytes
from index 4 through the byte before the checksum. Use the lowest byte of the
sum. A mismatch indicates a corrupt response.
