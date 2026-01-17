from __future__ import annotations

import argparse
import asyncio
import logging

from .client import IFitBleClient
from .ftms_server import FtmsBleRelay, FtmsConfig


async def _run_server(args: argparse.Namespace) -> None:
    client = IFitBleClient(args.address, args.activation_code)
    config = FtmsConfig(name=args.name, update_interval=args.interval)
    relay = FtmsBleRelay(client, config)

    try:
        await relay.start()
        await asyncio.Event().wait()
    finally:
        await relay.stop()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an FTMS BLE relay for iFit")
    parser.add_argument("address", help="BLE address of the iFit equipment")
    parser.add_argument("activation_code", help="Activation code for iFit equipment")
    parser.add_argument("--name", default="iFit FTMS", help="BLE advertising name")
    parser.add_argument("--interval", type=float, default=1.0, help="Update interval seconds")
    return parser.parse_args()


def main() -> None:
    """Entry point for running the FTMS relay."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()
    asyncio.run(_run_server(args))


if __name__ == "__main__":
    main()
