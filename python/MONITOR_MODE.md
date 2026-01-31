# Monitor-Only Mode Implementation

## Summary

Added **monitor-only mode** to zwifit's Python iFit BLE client, allowing users to monitor their treadmill **without an activation code**. This uses the NongoFit approach for read-only access.

## Changes Made

### 1. Updated `IFitBleClient.__init__` ([client.py](ifit_ble/client.py))

Added new `monitor_only` parameter:

```python
client = IFitBleClient(address, monitor_only=True)  # No activation code needed!
```

### 2. Added `_initialize_monitor_only` method

Initializes the client for read-only monitoring without authentication:
- Skips ENABLE command (no activation code needed)
- Creates minimal equipment info with basic characteristics
- Uses TREADMILL equipment type

### 3. Added `monitor_basic_state` method

Returns NongoFit-compatible basic monitoring data:

```python
state = await client.monitor_basic_state()
# Returns: {'pace': 5.0, 'incline': 2.5, 'distance': 1000, 'pulse': 120, 'timer': 300}
```

## Usage Examples

### Simple Monitoring (No Activation Code)

```python
from ifit_ble import IFitBleClient

# Create client in monitor-only mode
client = IFitBleClient("AA:BB:CC:DD:EE:FF", monitor_only=True)
await client.connect()

# Get basic state
state = await client.monitor_basic_state()
print(f"Speed: {state['pace']} kph, Incline: {state['incline']}%")

# Read specific characteristics
values = await client.read_characteristics(["Kph", "Incline", "CurrentTime"])

await client.disconnect()
```

### See Full Examples

- **[monitor_example.py](monitor_example.py)** - Complete monitoring demo with live updates
- **[modes_example.py](modes_example.py)** - Comparison of all three initialization modes

## Three Initialization Modes

| Mode | Code Required? | Read | Write | Example |
|------|----------------|------|-------|---------|
| **Monitor-only** | ❌ No | ✅ | ❌ | `IFitBleClient(addr, monitor_only=True)` |
| **Hardcoded model** | ❌ No | ✅ | ✅ | `IFitBleClient(addr, model="proform_treadmill_l6_0s")` |
| **Standard** | ✅ Yes | ✅ | ✅ | `IFitBleClient(addr, activation_code="12345678")` |

## What Monitor-Only Mode Provides

### ✅ Works Without Activation Code
- No authentication required
- Uses NongoFit's approach (WRITE_AND_READ without ENABLE)
- Perfect for users who don't have/need activation codes

### ✅ Basic Monitoring
Read these 5 essential values:
- **Pace** (Kph) - Current speed
- **Incline** - Current incline percentage
- **Distance** (CurrentDistance) - Total distance
- **Pulse** - Heart rate
- **Timer** (CurrentTime) - Workout duration

### ✅ Compatible with NongoFit
- Same read-only approach
- Returns data in compatible format
- Can be used as a drop-in replacement for NongoFit

### ✅ Can Read More Characteristics
Not limited to just 5 values - can read any characteristic:

```python
# Read additional characteristics
values = await client.read_characteristics([
    "Kph", "Incline", "CurrentDistance", "Pulse", 
    "CurrentTime", "Mode", "CurrentKph", "CurrentIncline"
])
```

## Limitations

### ❌ Cannot Write (Read-Only)
Monitor-only mode cannot control the treadmill:

```python
# This will FAIL in monitor-only mode
await client.write_characteristics({"Kph": 5.0})  # Error!
```

For write access, use:
- Standard mode with activation code
- Hardcoded model sequences (for supported models)

### ❌ Limited Equipment Info
Monitor-only mode doesn't query:
- Equipment capabilities
- Supported commands
- Min/max values
- Metric settings

## Why This Matters

### For Users
- **No activation code needed** for workout logging
- **Simple monitoring** without complex setup
- **Compatible** with NongoFit approach

### For Developers
- **Validates** zwifit's protocol implementation
- **Proves** read-only access doesn't need authentication
- **Extends** functionality beyond original scope

## Testing

Run the monitor example:

```bash
python monitor_example.py [MAC_ADDRESS]
```

Or compare all modes:

```bash
python modes_example.py
```

## Protocol Validation

This implementation **confirms** that:
1. ✅ WRITE_AND_READ command works without ENABLE
2. ✅ NongoFit's hardcoded request is valid zwifit protocol
3. ✅ Authentication is only needed for write operations
4. ✅ zwifit can do everything NongoFit does (plus more)

## Related Documentation

- **[PROTOCOL_COMPARISON.md](PROTOCOL_COMPARISON.md)** - Full zwifit vs NongoFit comparison
- **[nongofit_analysis.md](nongofit_analysis.md)** - NongoFit request decoding
- **[client.py](ifit_ble/client.py)** - Implementation
- **[README.md](ifit_ble/README.md)** - Updated usage guide
