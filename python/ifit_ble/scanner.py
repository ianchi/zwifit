from __future__ import annotations

from dataclasses import dataclass

from bleak import BleakScanner


@dataclass(frozen=True)
class IFitDevice:
    address: str
    name: str | None
    manufacturer_data: bytes


def _normalize_ble_code(code: str) -> str:
    cleaned = code.strip().lower()
    if len(cleaned) != 4 or any(c not in "0123456789abcdef" for c in cleaned):
        raise ValueError("BLE code must be a 4-character hex string")
    return cleaned


async def find_ifit_device(code: str, timeout: float = 10.0) -> IFitDevice:
    normalized = _normalize_ble_code(code)
    suffix = bytes.fromhex(f"dd{normalized}")

    devices = await BleakScanner.discover(timeout=timeout)
    for device in devices:
        if not device.metadata:
            continue
        manufacturer_data = device.metadata.get("manufacturer_data")
        if not manufacturer_data:
            continue
        for payload in manufacturer_data.values():
            if payload.endswith(suffix):
                return IFitDevice(
                    address=device.address,
                    name=device.name,
                    manufacturer_data=payload,
                )

    raise TimeoutError("No iFit device found with the provided BLE code")
