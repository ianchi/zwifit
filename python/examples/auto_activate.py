#!/usr/bin/env python3
"""Example: Automatically discover and activate an iFit device by trying all codes.

This script demonstrates how to use the try_activation_codes() method to
automatically find the correct activation code for your equipment.
"""

import asyncio
import logging

from ifit_ble import IFitBleClient


async def main():
    """Connect to device and try activation codes until one works."""
    # Configure logging to see progress
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Replace with your device's BLE address
    device_address = "AA:BB:CC:DD:EE:FF"
    
    # Create client without specifying activation code
    client = IFitBleClient(device_address)
    
    try:
        print(f"Connecting to {device_address}...")
        
        # Try all activation codes until one works
        # This will automatically connect and test each code
        code, model = await client.try_activation_codes()
        
        print(f"\n{'='*60}")
        print(f"SUCCESS! Equipment activated")
        print(f"Model: {model}")
        print(f"Activation code: {code}")
        print(f"{'='*60}\n")
        
        # Now you can use the client normally
        if client.equipment_information:
            print(f"Equipment type: {client.equipment_information.equipment.name}")
            print(f"Characteristics: {len(client.equipment_information.characteristics)}")
        
        # Read current values
        print("\nReading current equipment state...")
        values = await client.read_current_values()
        for name, value in values.items():
            print(f"  {name}: {value}")
        
        # You can save the successful code for future use
        print(f"\nFor future connections, use:")
        print(f'  client = IFitBleClient("{device_address}", activation_code="{code}")')
        
    except ValueError as e:
        print(f"\nFailed to activate: {e}")
        print("\nPossible reasons:")
        print("  - Device is not an iFit equipment")
        print("  - Device requires a new/unknown activation code")
        print("  - Device is already in use by another application")
        
    except Exception as e:
        print(f"\nError: {e}")
        
    finally:
        if client._client.is_connected:
            await client.disconnect()
            print("\nDisconnected")


if __name__ == "__main__":
    asyncio.run(main())
