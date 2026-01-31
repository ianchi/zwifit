#!/usr/bin/env python3
"""
Simple wrapper to run ifit CLI commands.
Usage: python ifit.py <command> [args...]
"""
import sys
from ifit_ble.cli import main

if __name__ == "__main__":
    main()
