#!/usr/bin/env python3
"""
Re-analyze considering NongoFit's response structure.

NongoFit's parse_response strips:
- Device info (3 bytes)
- Response type (4 bytes)

So the slices start AFTER 7 bytes of metadata.
"""

# From NongoFit responses.py comments:
# 010402 2e04 2e0202a0002c01710014000000
# MMMMMM TTTT -------------------------
# Device Metadata (M): 3 bytes (010402)
# Type (T): 4 bytes (2e042e02)
# Data starts at byte 7

NONGOFIT_READS = [
    (0, 'Kph', 2),              # Double
    (1, 'Incline', 2),          # Double  
    (3, 'Unknown', 1),          # ?
    (4, 'CurrentDistance', 4),  # 4-byte int
    (10, 'Pulse', 4),           # Pulse struct
    (12, 'Mode', 1),            # 1-byte
    (15, 'Unknown', 1),         # ?
    (20, 'CurrentTime', 4),     # 4-byte int
    (21, 'CurrentCalories', 4), # Calories
    (46, 'X4', 2),              # 2-byte int
    (52, 'AverageIncline', 2),  # Double
    (54, 'Unknown', 1),         # ?
    (71, 'X6', 2),              # 2-byte int
    (75, 'Unknown', 1),         # ?
    (76, 'Unknown', 1),         # ?
]

print("=" * 80)
print("NONGOFIT RESPONSE STRUCTURE (from responses.py)")
print("=" * 80)

print("""
NongoFit's parse_response processes:
  - Bytes 0-2:  Device metadata (stripped)
  - Bytes 3-6:  Response type (stripped)
  - Bytes 7+:   Actual data

NongoFit's _slices are relative to byte 7 (after stripping metadata).
""")

nongofit_slices = {
    "PACE": (1, 3),        # In data section (after 7-byte header)
    "INCLINE": (3, 5),     
    "DISTANCE": (7, 9),    
    "PULSE": (11, 12),     
    "TIMER": (18, 20),     
}

print("NongoFit's slices (relative to start of DATA section):")
for name, (start, end) in nongofit_slices.items():
    abs_start = start + 7  # Absolute position in response
    abs_end = end - 1 + 7
    print(f"  {name:12s}: data[{start:2d}:{end:2d}] = absolute bytes {abs_start:2d}-{abs_end:2d}")

print("\n" + "=" * 80)
print("ZWIFIT RESPONSE STRUCTURE")
print("=" * 80)

print("""
zwifit's WRITE_AND_READ response:
  - Bytes 0-7:  Protocol header (equipment, command, status, etc.)
  - Bytes 8+:   Characteristic values in ID order
""")

print("zwifit characteristic layout (starting at byte 8):")
offset = 8
for char_id, char_name, size in NONGOFIT_READS:
    end_offset = offset + size - 1
    print(f"  Bytes {offset:2d}-{end_offset:2d} (size {size}): ID {char_id:3d} = {char_name}")
    offset += size

print("\n" + "=" * 80)
print("KEY INSIGHT")
print("=" * 80)

print("""
NongoFit and zwifit have DIFFERENT response structures:

NongoFit response:
  [Device:3][Type:4][Data:variable]
  Total: 7+ bytes header

zwifit response:  
  [Header:8][Data:variable]
  Total: 8+ bytes header

But wait... NongoFit's packet_reader STRIPS the BLE framing!
The actual BLE response would have zwifit's 8-byte header,
then NongoFit adds its own interpretation of device/type.

This suggests NongoFit is parsing a SUBSET of the full response data
using empirically discovered offsets, not the full protocol structure.
""")

print("\n" + "=" * 80)
print("ALTERNATIVE THEORY")
print("=" * 80)

print("""
What if NongoFit's response type (0x2e042e02) IS part of the data payload?

Looking at zwifit's structure more carefully:
  - Response always has 8-byte header
  - Then characteristic values in order
  
NongoFit might be:
  1. Reading the zwifit response
  2. Misinterpreting bytes 3-6 as a "type" field
  3. Parsing the rest as data

Let's check if NongoFit's offsets could match if we account
for this misalignment...
""")

# NongoFit starts parsing at byte 7, but what if zwifit data starts at byte 8?
# There's a 1-byte difference!

print("Adjusted comparison (NongoFit offset + 7 vs zwifit offset):")
print("-" * 80)

zwifit_map = {}
offset = 8
for char_id, char_name, size in NONGOFIT_READS:
    zwifit_map[char_id] = (offset, size, char_name)
    offset += size

# NongoFit characteristic mapping (guessed)
nf_to_zwifit = {
    "PACE": 0,       # Kph
    "INCLINE": 1,    # Incline
    "DISTANCE": 4,   # CurrentDistance
    "PULSE": 10,     # Pulse
    "TIMER": 20,     # CurrentTime
}

for nf_name, char_id in nf_to_zwifit.items():
    nf_start, nf_end = nongofit_slices[nf_name]
    nf_abs = nf_start + 7  # NongoFit absolute position
    
    zwifit_start, size, zwifit_name = zwifit_map[char_id]
    
    diff = nf_abs - zwifit_start
    match = "✓" if diff == 0 else "✗"
    
    print(f"{match} {nf_name:12s} (ID {char_id:2d}): NF @{nf_abs:2d}, zwifit @{zwifit_start:2d}, diff={diff:+d}")

print("\n" + "=" * 80)
print("FINAL ANALYSIS")
print("=" * 80)

print("""
The offsets are close but offset by 1 byte!

This could mean:
1. NongoFit's byte counting is off by one (common bug)
2. Different response framing (NongoFit strips 7, zwifit uses 8)
3. NongoFit discovered empirical offsets through trial-and-error
4. The actual device response has subtle differences from zwifit's model

CONCLUSION:
NongoFit uses HARDCODED OFFSETS that work for their specific use case,
but aren't aligned with zwifit's structured protocol parsing.

Both likely work with the actual hardware, just using different
approaches to extract the same data.
""")
