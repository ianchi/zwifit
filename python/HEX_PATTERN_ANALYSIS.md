## Activation Code Hex Pattern Analysis

### Summary of Findings

I analyzed 45 activation codes from the `codes_reverse.csv` file and discovered clear structural patterns:

---

## 🔍 Code Structure (36 bytes total)

```
┌─────────┬──────────────┬────────────────────────────────────┬─────────────────┐
│ Byte 0  │   Byte 1     │         Bytes 2-31                 │   Bytes 32-35   │
├─────────┼──────────────┼────────────────────────────────────┼─────────────────┤
│ Type    │ Sub-version  │    Activation Data (30 bytes)      │ Protocol Marker │
│ 04/07   │   Varies     │       Device-specific              │  XX 02 00 00    │
└─────────┴──────────────┴────────────────────────────────────┴─────────────────┘
```

---

## 📊 Pattern Details

### 1. **Byte 0: Type Flag**
- **0x04**: 17 codes (38%) - Older/Type A devices
- **0x07**: 28 codes (62%) - Newer/Type B devices

### 2. **Byte 1: Sub-version**
Most common combinations:
- **07-01**: 22 codes (49%) - Most common newer type
- **04-00**: 17 codes (38%) - All older type devices

### 3. **Bytes 2-31: Activation Data (30 bytes)**
- Appears cryptographically derived or device-specific
- High entropy (25-30 unique bytes out of 30)
- No obvious repeating patterns
- No simple XOR or checksum relationship detected

### 4. **Bytes 32-35: Suffix Marker**
Always ends with: `XX 02 00 00`

Where byte 32 (XX) is one of:
- **0x80**: 18 codes (40%) - Most common
- **0x98**: 12 codes (27%)
- **0xa0**: 8 codes (18%)
- **0x88**: 4 codes (9%)
- **0x90**: 3 codes (7%)

Bytes 33-35 are **ALWAYS**: `02 00 00` (protocol marker)

---

## 🔢 Distribution by Type

### Type 0x04 Devices (Older Generation)
```
0400ee44... - proform_treadmill_l6_0s
040061d8... - nordictrack10
040036a4... - proform_505_cst_80_44
0400fda8... - proform_performance_300i
04005d28... - proform_performance_400i
04001978... - proform_treadmill_c700
...
```

### Type 0x07 Devices (Newer Generation)
```
0701c86c... - proform_treadmill_995i
07e6dad4... - nordictrack_series_7
0798e938... - proform_carbon_tl
07015770... - proform_treadmill_1500_pro
07018d68... - nordictrack_tseries5_treadmill
070193c0... - proform_treadmill_c960i
...
```

---

## 🎯 Key Observations

1. **Fixed Structure**: All codes are exactly 36 bytes (72 hex characters)

2. **Version Evolution**: The 0x04 vs 0x07 first byte likely indicates protocol version or device generation

3. **Consistent Terminator**: The last 3 bytes are always `02 00 00`, suggesting a protocol version marker

4. **Unique Activation Data**: The middle 30 bytes appear to be unique per device, likely:
   - Cryptographic key material
   - Device serial number hash
   - Encrypted activation token

5. **Related Devices Show No Pattern**: Even similar models (e.g., ProForm Carbon TL variants) have completely different activation data, suggesting each code is uniquely generated per device instance

---

## 💡 Implications

- **Not Easily Generatable**: The activation data doesn't follow a simple algorithmic pattern
- **Likely Server-Generated**: Codes are probably issued by iFit servers based on device info
- **Cryptographic Nature**: High entropy suggests encryption or secure hashing
- **Protocol Versioning**: Multiple code versions coexist (0x04 and 0x07)

---

## 📈 Visual Breakdown Example

```
Code: 0400ee4490ea42a8f456b62c88e25ad03c8e1e94e07af278c446c67cf872eaa080020000
      │││││└─┬──┘└──────────────────┬────────────────────────┘└───┬──┘
      │││││  │                       │                              │
      │││││  │                       │                              └─ Suffix: 80 02 00 00
      │││││  │                       │
      │││││  │                       └─ Data: 90ea42a8...f872eaa0 (30 bytes)
      │││││  │
      │││││  └─ Sub-version: 0xee44
      │││││
      ││││└─ Type: 0x04
```

---

## 🔐 Security Note

The activation codes appear to be designed to prevent:
- Reverse engineering
- Code generation without server access
- Code reuse across devices

Each code is unique and tied to specific device characteristics.
