#!/usr/bin/env python3
"""
Compare BLE advertising data between real device and simulated server.
"""
import asyncio
from bleak import BleakScanner


async def scan_all_devices():
    """Scan and show all BLE devices with their advertising data."""
    print("Scanning for BLE devices...")
    print("=" * 80)
    
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    
    for device, adv_data in devices.values():
        # Look for iFit-related devices
        is_ifit = False
        
        # Check manufacturer data
        if adv_data.manufacturer_data:
            for company_id, payload in adv_data.manufacturer_data.items():
                # Check if it ends with dd**50 or dd**60 pattern
                if len(payload) >= 3 and payload[-3] == 0xdd:
                    is_ifit = True
        
        # Check service UUIDs
        if '00001533' in str(adv_data.service_uuids).lower():
            is_ifit = True
        
        if not is_ifit:
            continue
            
        print(f"\n📱 Device: {device.name or 'Unknown'}")
        print(f"   Address: {device.address}")
        print(f"   RSSI: {adv_data.rssi} dBm")
        
        # Manufacturer data
        if adv_data.manufacturer_data:
            for company_id, payload in adv_data.manufacturer_data.items():
                print(f"   Company ID: 0x{company_id:04x}")
                print(f"   Manufacturer Data: {payload.hex()}")
                print(f"   Manufacturer Data (bytes): {' '.join([f'{b:02x}' for b in payload])}")
        else:
            print(f"   Manufacturer Data: NONE")
        
        # Service UUIDs
        if adv_data.service_uuids:
            print(f"   Service UUIDs advertised:")
            for uuid in adv_data.service_uuids:
                print(f"      - {uuid}")
        else:
            print(f"   Service UUIDs advertised: NONE")
        
        # Service data
        if adv_data.service_data:
            print(f"   Service Data:")
            for uuid, data in adv_data.service_data.items():
                print(f"      {uuid}: {data.hex()}")
        
        # Local name
        if adv_data.local_name:
            print(f"   Local Name: {adv_data.local_name}")
        
        # TX power
        if adv_data.tx_power is not None:
            print(f"   TX Power: {adv_data.tx_power}")
        
        print("-" * 80)
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(scan_all_devices())
