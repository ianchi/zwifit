from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from .client import IFitBleClient
from .scanner import find_ifit_device, find_all_ifit_devices

# Optional FTMS server support
try:
    from .ftms_server import FtmsBleRelay, FtmsConfig
    FTMS_AVAILABLE = True
except ImportError:
    FTMS_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


async def _discover_devices(args: argparse.Namespace) -> None:
    """Discover iFit devices using BLE code."""
    print(f"Scanning for iFit device with code '{args.code}'...")
    try:
        device = await find_ifit_device(args.code, timeout=args.timeout)
        print(f"\n✓ Found device:")
        print(f"  Address: {device.address}")
        print(f"  Name: {device.name or 'Unknown'}")
        print(f"  Manufacturer Data: {device.manufacturer_data.hex()}")
    except TimeoutError:
        print(f"\n✗ No device found with code '{args.code}' after {args.timeout}s")
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


async def _discover_activation_code(args: argparse.Namespace) -> None:
    """Discover activation code by intercepting manufacturer app."""
    try:
        from .activation_discovery import discover_activation_code
    except ImportError as e:
        print("\n✗ Activation code discovery requires additional dependencies:")
        print("  pip install bless")
        print(f"\nError: {e}")
        sys.exit(1)
    
    try:
        activation_code = await discover_activation_code(
            args.code,
            treadmill_address=args.address,
            timeout=args.timeout
        )
        
        # Save to a file for easy reference
        import os
        config_file = os.path.expanduser("~/.ifit_activation_codes")
        with open(config_file, "a") as f:
            address = args.address or "discovered"
            f.write(f"{args.code},{address},{activation_code}\n")
        
        print(f"Activation code saved to: {config_file}\n")
        
    except ImportError as e:
        print(f"\n✗ Missing dependencies: {e}")
        print("Install with: pip install bless")
        sys.exit(1)
    except TimeoutError as e:
        print(f"\n✗ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Discovery failed: {e}")
        LOGGER.error("Discovery error", exc_info=True)
        sys.exit(1)


async def _connect(args: argparse.Namespace) -> None:
    """Connect to equipment using activation code."""
    if not args.code:
        print("\n✗ Activation code required. Use --code argument.")
        print("\nExample: ifit connect AA:BB:CC:DD:EE:FF --code 0766D40AD0C82C90")
        print("\nTip: Use 'ifit try-codes' to automatically find the right activation code.")
        sys.exit(1)
    
    print(f"Connecting to {args.address} using activation code {args.code}...\n")
    
    client = IFitBleClient(args.address, activation_code=args.code)
    try:
        await client.connect()
        print("\n✓ Connected successfully!")
        
        # Show basic info
        info = client.equipment_information
        if info:
            print(f"\nEquipment Type: {info.equipment.name}")
            if info.serial_number:
                print(f"Serial Number: {info.serial_number}")
            if info.firmware_version:
                print(f"Firmware Version: {info.firmware_version}")
            print(f"Characteristics: {len(info.characteristics)}")
            print(f"Capabilities: {len(info.supported_capabilities)}")
        
        print("\nDevice is ready for use. Press Ctrl+C to disconnect.")
        
        # Keep connection alive
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nDisconnecting...")
    
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        LOGGER.error("Connection error", exc_info=True)
        raise
    
    finally:
        try:
            await client.disconnect()
            print("Disconnected.")
        except Exception as e:
            LOGGER.debug(f"Error during disconnect: {e}")


async def _try_codes(args: argparse.Namespace) -> None:
    """Try all activation codes until one works."""
    print(f"Attempting to activate {args.address}...")
    print("This may take a while as we try different activation codes.\n")
    
    client = IFitBleClient(args.address)
    try:
        code, model = await client.try_activation_codes(max_attempts=args.max_attempts)
        
        print(f"\n✓ Success! Device activated with code: {code}")
        print(f"Model: {model}\n")
        print("Save this activation code for future use:")
        print(f"  ifit connect {args.address} --code {code}")
        
    except ValueError as e:
        print(f"\n✗ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        LOGGER.error("Try codes error", exc_info=True)
        sys.exit(1)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

async def _list_devices(args: argparse.Namespace) -> None:
    """List all iFit devices in range."""
    print(f"Scanning for iFit devices (timeout: {args.timeout}s)...")
    
    try:
        devices = await find_all_ifit_devices(timeout=args.timeout)
        
        if not devices:
            print("\n✗ No iFit devices found")
            sys.exit(1)
        
        print(f"\n✓ Found {len(devices)} iFit device(s):\n")
        for i, device in enumerate(devices, 1):
            # Extract BLE code from manufacturer data (reverse byte order for display)
            ble_code = device.manufacturer_data[-2:].hex()
            # Reverse pairs: dd50 -> 50dd
            ble_code_display = ble_code[2:4] + ble_code[0:2]
            print(f"{i}. {device.name or 'Unknown Device'}")
            print(f"   Address: {device.address}")
            print(f"   BLE Code: {ble_code_display}")
            print(f"   Manufacturer Data: {device.manufacturer_data.hex()}")
            print()
    
    except Exception as e:
        print(f"\n✗ Error during scan: {e}")
        sys.exit(1)


async def _show_info(args: argparse.Namespace) -> None:
    """Connect and display equipment information."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        print("Connecting to device...")
        await client.connect()
        
        info = client.equipment_information
        if not info:
            print("✗ Failed to retrieve equipment information")
            sys.exit(1)
        
        print(f"\n✓ Equipment Information:")
        print(f"  Type: {info.equipment.name}")
        print(f"  Characteristics: {len(info.characteristics)}")
        print(f"  Supported Capabilities: {len(info.supported_capabilities)}")
        
        if args.verbose:
            print(f"\n  Values:")
            for key, value in sorted(info.values.items()):
                print(f"    {key}: {value}")
            
            print(f"\n  Characteristics:")
            for char in info.characteristics:
                print(f"    {char.name} (ID: {char.id})")
            
            # Show supported commands
            try:
                supported_commands = await client.get_supported_commands()
                print(f"\n  Supported Commands: {supported_commands}")
            except Exception as e:
                LOGGER.debug(f"Could not fetch supported commands: {e}")
        
    finally:
        await client.disconnect()


async def _read_values(args: argparse.Namespace) -> None:
    """Read characteristic values from the equipment."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        await client.connect()
        
        if args.current:
            values = await client.read_current_values()
        else:
            # Parse characteristic names or IDs
            characteristics = []
            for char in args.characteristics:
                try:
                    characteristics.append(int(char))
                except ValueError:
                    characteristics.append(char)
            values = await client.read_characteristics(characteristics)
        
        if args.json:
            print(json.dumps(values, indent=2))
        else:
            print("\nCharacteristic Values:")
            for key, value in sorted(values.items()):
                print(f"  {key}: {value}")
    
    finally:
        await client.disconnect()


async def _write_values(args: argparse.Namespace) -> None:
    """Write characteristic values to the equipment."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        await client.connect()
        
        # Parse key=value pairs
        values: dict[str, Any] = {}
        for pair in args.values:
            if '=' not in pair:
                print(f"✗ Invalid format: {pair}. Use KEY=VALUE")
                sys.exit(1)
            
            key, value_str = pair.split('=', 1)
            # Try to parse as number, otherwise keep as string
            try:
                value: Any = float(value_str)
                if value.is_integer():
                    value = int(value)
            except ValueError:
                value = value_str
            
            values[key] = value
        
        print(f"Writing values: {values}")
        await client.write_characteristics(values)
        print("✓ Values written successfully")
    
    finally:
        await client.disconnect()


async def _control_treadmill(args: argparse.Namespace) -> None:
    """Send control commands to the treadmill."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        await client.connect()
        
        if args.command == "start":
            await client.write_characteristics({"Mode": 1})
            print("✓ Treadmill started")
        
        elif args.command == "stop":
            await client.write_characteristics({"Mode": 0})
            print("✓ Treadmill stopped")
        
        elif args.command == "speed":
            if args.value is None:
                print("✗ Speed value required. Use --value")
                sys.exit(1)
            await client.write_characteristics({"Kph": args.value})
            print(f"✓ Speed set to {args.value} km/h")
        
        elif args.command == "incline":
            if args.value is None:
                print("✗ Incline value required. Use --value")
                sys.exit(1)
            await client.write_characteristics({"Incline": args.value})
            print(f"✓ Incline set to {args.value}%")
        
        elif args.command == "calibrate-incline":
            await client.calibrate_incline()
            print("✓ Incline calibration started")
    
    finally:
        await client.disconnect()


async def _monitor(args: argparse.Namespace) -> None:
    """Monitor real-time values from the equipment."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        await client.connect()
        print("Monitoring equipment (Ctrl+C to stop)...\n")
        
        while True:
            values = await client.read_current_values()
            
            # Clear line and print values
            output = " | ".join(f"{k}: {v}" for k, v in sorted(values.items()))
            print(f"\r{output}", end="", flush=True)
            
            await asyncio.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
    finally:
        await client.disconnect()


async def _monitor_only(args: argparse.Namespace) -> None:
    """Monitor equipment in read-only mode (no activation code needed)."""
    print(f"Connecting to {args.address} in monitor-only mode...")
    print("(No activation code required - read-only access)\n")
    
    client = IFitBleClient(args.address, monitor_only=True)
    try:
        await client.connect()
        print("✓ Connected successfully!\n")
        print("Monitoring basic state (Ctrl+C to stop)...\n")
        
        # Print header
        print(f"{'Time':>6} | {'Pace (kph)':>10} | {'Incline (%)':>11} | {'Distance':>10} | {'Pulse (bpm)':>11} | {'Timer (s)':>10}")
        print("-" * 80)
        
        iteration = 0
        while True:
            state = await client.monitor_basic_state()
            
            print(f"{iteration:>6} | "
                  f"{state['pace']:>10.1f} | "
                  f"{state['incline']:>11.1f} | "
                  f"{state['distance']:>10} | "
                  f"{state['pulse']:>11} | "
                  f"{state['timer']:>10}")
            
            iteration += 1
            await asyncio.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
    finally:
        await client.disconnect()
        print("Disconnected.")


async def _list_capabilities(args: argparse.Namespace) -> None:
    """List supported capabilities and commands."""
    client = IFitBleClient(args.address, args.activation_code)
    try:
        await client.connect()
        
        info = client.equipment_information
        if not info:
            print("✗ Failed to retrieve equipment information")
            sys.exit(1)
        
        print(f"\n✓ Supported Capabilities ({len(info.supported_capabilities)}):")
        for cap_id in sorted(info.supported_capabilities):
            print(f"  ID: {cap_id}")
        
        try:
            supported_commands = await client.get_supported_commands()
            print(f"\n✓ Supported Commands ({len(supported_commands)}):")
            for cmd_id in sorted(supported_commands):
                print(f"  ID: {cmd_id}")
        except Exception as e:
            print(f"\n✗ Could not fetch supported commands: {e}")
        
    finally:
        await client.disconnect()


async def _run_ftms_relay(args: argparse.Namespace) -> None:
    """Run the FTMS relay server until interrupted."""
    if not FTMS_AVAILABLE:
        print("✗ FTMS server not available. Install with: pip install -e \".[ftms]\"")
        sys.exit(1)
    
    client = IFitBleClient(args.address, args.activation_code)
    config = FtmsConfig(name=args.name, update_interval=args.interval)
    relay = FtmsBleRelay(client, config)

    try:
        print(f"Starting FTMS relay server '{args.name}'...")
        await relay.start()
        print("✓ Server running (Ctrl+C to stop)")
        # Block forever; BLE server lifecycle managed by ctrl+c.
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        await relay.stop()
        print("✓ Server stopped")


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the iFit BLE tool."""
    parser = argparse.ArgumentParser(
        description="iFit BLE Command-Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all iFit devices in range
  ifit list
  ifit list --timeout 20
  
  # Discover specific device by BLE code
  ifit discover 1a2b
  
  # Discover activation code (requires manufacturer app)
  ifit discover-activation 1a2b
  
  # Try all activation codes automatically
  ifit try-codes AA:BB:CC:DD:EE:FF
  ifit try-codes AA:BB:CC:DD:EE:FF --max-attempts 10
  
  # Connect with known activation code
  ifit connect AA:BB:CC:DD:EE:FF --code 0766D40AD0C82C90
  
  # Monitor without activation code (read-only, no control)
  ifit monitor-only AA:BB:CC:DD:EE:FF
  ifit monitor-only AA:BB:CC:DD:EE:FF --interval 0.5
  
  # Show equipment information
  ifit info AA:BB:CC:DD:EE:FF 12345678
  ifit info AA:BB:CC:DD:EE:FF 12345678 --verbose
  
  # List supported capabilities and commands
  ifit capabilities AA:BB:CC:DD:EE:FF 12345678
  
  # Read current values
  ifit read AA:BB:CC:DD:EE:FF 12345678 --current
  ifit read AA:BB:CC:DD:EE:FF 12345678 Kph Incline --json
  
  # Write values
  ifit write AA:BB:CC:DD:EE:FF 12345678 Kph=5.0 Incline=2
  
  # Control treadmill
  ifit control AA:BB:CC:DD:EE:FF 12345678 speed --value 5.0
  ifit control AA:BB:CC:DD:EE:FF 12345678 start
  
  # Monitor in real-time (with activation code)
  ifit monitor AA:BB:CC:DD:EE:FF 12345678
  ifit monitor AA:BB:CC:DD:EE:FF 12345678 --interval 0.5
  
  # Start FTMS relay server
  ifit ftms AA:BB:CC:DD:EE:FF 12345678 --name "My Treadmill"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute", required=True)
    
    # Connect command (uses activation code)
    connect_parser = subparsers.add_parser(
        "connect",
        help="Connect to equipment using activation code"
    )
    connect_parser.add_argument("address", help="BLE address of the iFit equipment")
    connect_parser.add_argument(
        "--code",
        help="Activation code (use 'try-codes' to auto-discover)"
    )
    connect_parser.set_defaults(func=_connect)
    
    # Try codes command
    try_codes_parser = subparsers.add_parser(
        "try-codes",
        help="Try all activation codes until one works"
    )
    try_codes_parser.add_argument("address", help="BLE address of the iFit equipment")
    try_codes_parser.add_argument(
        "--max-attempts",
        type=int,
        help="Maximum number of codes to try (default: all)"
    )
    try_codes_parser.set_defaults(func=_try_codes)
    
    # List devices command
    list_parser = subparsers.add_parser(
        "list",
        help="List all iFit devices in range"
    )
    list_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Scan timeout in seconds (default: 10.0)"
    )
    list_parser.set_defaults(func=_list_devices)
    
    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover iFit devices by BLE code"
    )
    discover_parser.add_argument(
        "code",
        help="4-character BLE code displayed on equipment"
    )
    discover_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Scan timeout in seconds (default: 10.0)"
    )
    discover_parser.set_defaults(func=_discover_devices)
    
    # Discover activation command
    discover_activation_parser = subparsers.add_parser(
        "discover-activation",
        help="Discover activation code by intercepting manufacturer app (advanced)"
    )
    discover_activation_parser.add_argument(
        "code",
        help="4-character BLE code displayed on equipment"
    )
    discover_activation_parser.add_argument(
        "--address",
        help="BLE address of the equipment (optional, will scan if not provided)"
    )
    discover_activation_parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout in seconds to wait for activation code (default: 60.0)"
    )
    discover_activation_parser.set_defaults(func=_discover_activation_code)
    
    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Display equipment information"
    )
    info_parser.add_argument("address", help="BLE address of the iFit equipment")
    info_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    info_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed information")
    info_parser.set_defaults(func=_show_info)
    
    # Read command
    read_parser = subparsers.add_parser(
        "read",
        help="Read characteristic values"
    )
    read_parser.add_argument("address", help="BLE address of the iFit equipment")
    read_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    read_parser.add_argument(
        "characteristics",
        nargs="*",
        help="Characteristic names or IDs to read"
    )
    read_parser.add_argument(
        "--current",
        action="store_true",
        help="Read commonly updated values (Kph, CurrentKph, CurrentIncline, Pulse, Mode)"
    )
    read_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    read_parser.set_defaults(func=_read_values)
    
    # Write command
    write_parser = subparsers.add_parser(
        "write",
        help="Write characteristic values"
    )
    write_parser.add_argument("address", help="BLE address of the iFit equipment")
    write_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    write_parser.add_argument(
        "values",
        nargs="+",
        help="Key=Value pairs to write (e.g., Kph=5.0 Incline=2)"
    )
    write_parser.set_defaults(func=_write_values)
    
    # Control command
    control_parser = subparsers.add_parser(
        "control",
        help="Send control commands to treadmill"
    )
    control_parser.add_argument("address", help="BLE address of the iFit equipment")
    control_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    control_parser.add_argument(
        "action",
        choices=["start", "stop", "speed", "incline", "calibrate-incline"],
        help="Control action to perform"
    )
    control_parser.add_argument(
        "--value",
        type=float,
        help="Value for speed (km/h) or incline (%%)"
    )
    control_parser.set_defaults(func=_control_treadmill)
    
    # Monitor command (with activation)
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Monitor real-time values from equipment (requires activation code)"
    )
    monitor_parser.add_argument("address", help="BLE address of the iFit equipment")
    monitor_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    monitor_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    monitor_parser.set_defaults(func=_monitor)
    
    # Monitor-only command (no activation needed)
    monitor_only_parser = subparsers.add_parser(
        "monitor-only",
        help="Monitor equipment without activation code (read-only, NongoFit mode)"
    )
    monitor_only_parser.add_argument("address", help="BLE address of the iFit equipment")
    monitor_only_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    monitor_only_parser.set_defaults(func=_monitor_only)
    
    # Capabilities command
    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="List supported capabilities and commands"
    )
    capabilities_parser.add_argument("address", help="BLE address of the iFit equipment")
    capabilities_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    capabilities_parser.set_defaults(func=_list_capabilities)
    
    # FTMS relay command
    ftms_parser = subparsers.add_parser(
        "ftms",
        help="Run FTMS BLE relay server"
    )
    ftms_parser.add_argument("address", help="BLE address of the iFit equipment")
    ftms_parser.add_argument("activation_code", help="Activation code for iFit equipment")
    ftms_parser.add_argument(
        "--name",
        default="iFit FTMS",
        help="BLE advertising name (default: 'iFit FTMS')"
    )
    ftms_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    ftms_parser.set_defaults(func=_run_ftms_relay)
    
    return parser.parse_args()


def main() -> None:
    """Entry point for the iFit CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s"
    )
    
    args = _parse_args()
    
    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
    except Exception as e:
        LOGGER.error("Error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
