from .client import IFitBleClient
from .protocol import (
    BLE_UUIDS,
    CHARACTERISTICS,
    CAPABILITIES,
    Command,
    EquipmentInformation,
    Mode,
    PulseSource,
    SportsEquipment,
    WriteValue,
)
from .scanner import IFitDevice, find_ifit_device

# Optional activation discovery
try:
    from .activation_discovery import discover_activation_code
    __activation_available = True
except ImportError:
    __activation_available = False

__all__ = [
    "BLE_UUIDS",
    "CAPABILITIES",
    "CHARACTERISTICS",
    "Command",
    "EquipmentInformation",
    "IFitBleClient",
    "IFitDevice",
    "Mode",
    "PulseSource",
    "SportsEquipment",
    "WriteValue",
    "find_ifit_device",
]

if __activation_available:
    __all__.append("discover_activation_code")

