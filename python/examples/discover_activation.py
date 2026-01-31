"""
Example: Discovering Activation Code

This example shows how to programmatically discover the activation code.
"""

import asyncio
from ifit_ble import discover_activation_code


async def main():
    # The BLE code displayed on your treadmill (4 characters)
    ble_code = "1a2b"  # Replace with your actual BLE code
    
    print("Starting activation code discovery...")
    print("Make sure your treadmill is on!")
    print()
    
    try:
        # This will:
        # 1. Find your treadmill
        # 2. Connect to it
        # 3. Start a BLE peripheral server
        # 4. Wait for you to connect via manufacturer app
        # 5. Capture and return the activation code
        
        activation_code = await discover_activation_code(
            ble_code=ble_code,
            timeout=60.0  # Wait up to 60 seconds
        )
        
        print(f"\nSuccess! Your activation code is: {activation_code}")
        print(f"\nYou can now use it with:")
        print(f"  ifit info <ADDRESS> {activation_code}")
        
    except ImportError:
        print("Error: Missing 'bless' package")
        print("Install with: pip install bless")
        
    except TimeoutError:
        print("Timeout: No activation code received")
        print("Make sure you connected via the manufacturer app")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
