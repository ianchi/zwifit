from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Iterable, Mapping

RESPONSE_OK_CODE = 2
MAX_BYTES_PER_MESSAGE = 18


class SportsEquipment(IntEnum):
    """Sports equipment identifiers used by the iFit protocol."""

    GENERAL = 2
    TREADMILL = 4


class PulseSource(IntEnum):
    """Pulse source identifiers reported by the equipment."""

    NO = 0
    HAND = 1
    UNKNOWN = 2
    UNKNOWN2 = 3
    BLE = 4


class Mode(IntEnum):
    """Equipment mode identifiers."""

    UNKNOWN = 0
    IDLE = 1
    ACTIVE = 2
    PAUSE = 3
    SUMMARY = 4
    SETTINGS = 7
    MISSING_SAFETY_KEY = 8


class Command(IntEnum):
    """Command identifiers used in request headers."""

    WRITE_AND_READ = 2
    CALIBRATE = 6
    SUPPORTED_CAPABILITIES = 128
    EQUIPMENT_INFORMATION = 129
    EQUIPMENT_REFERENCE = 130
    EQUIPMENT_FIRMWARE = 132
    SUPPORTED_COMMANDS = 136
    ENABLE = 144
    EQUIPMENT_SERIAL = 149


class MessageIndex(IntEnum):
    """Chunk index markers for BLE message framing."""

    HEADER = 0xFE
    EOF = 0xFF


@dataclass(frozen=True)
class Converter:
    """Converter describing buffer encoding/decoding for a characteristic."""

    size: int
    from_buffer: Callable[[bytes, int], Any]
    to_buffer: Callable[[bytearray, int, Any], int]


@dataclass(frozen=True)
class CharacteristicDefinition:
    """Definition of a characteristic and its converter."""

    name: str
    id: int
    read_only: bool
    converter: Converter | None


@dataclass(frozen=True)
class CapabilityDefinition:
    """Definition of a high-level capability and its characteristic id."""

    id: int
    characteristic_id: int


@dataclass
class EquipmentInformation:
    """Stateful equipment metadata and current values."""

    equipment: SportsEquipment
    characteristics: dict[int, CharacteristicDefinition]
    supported_capabilities: list[int] = field(default_factory=list)
    supported_commands: list[int] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    serial_number: str | None = None
    firmware_version: str | None = None
    reference_number: int | None = None


@dataclass(frozen=True)
class WriteValue:
    """Represents a write request for a single characteristic."""

    characteristic: CharacteristicDefinition
    value: Any


def _double_from_buffer(buffer: bytes, pos: int) -> float:
    """Decode a scaled uint16 (two decimals) from the buffer."""
    return int.from_bytes(buffer[pos : pos + 2], "little") / 100


def _double_to_buffer(buffer: bytearray, pos: int, value: float) -> int:
    """Encode a scaled uint16 (two decimals) into the buffer."""
    scaled = round(value * 100)
    buffer[pos : pos + 2] = int(scaled).to_bytes(2, "little")
    return pos + 2


def _bool_from_buffer(buffer: bytes, pos: int) -> bool:
    """Decode a boolean flag."""
    return buffer[pos] == 1


def _bool_to_buffer(buffer: bytearray, pos: int, value: bool) -> int:
    """Encode a boolean flag."""
    buffer[pos] = 1 if value else 0
    return pos + 1


def _uint8_from_buffer(buffer: bytes, pos: int) -> int:
    """Decode a uint8."""
    return buffer[pos]


def _uint8_to_buffer(buffer: bytearray, pos: int, value: int) -> int:
    """Encode a uint8."""
    buffer[pos] = int(value) & 0xFF
    return pos + 1


def _uint16_from_buffer(buffer: bytes, pos: int) -> int:
    """Decode a uint16."""
    return int.from_bytes(buffer[pos : pos + 2], "little")


def _uint16_to_buffer(buffer: bytearray, pos: int, value: int) -> int:
    """Encode a uint16."""
    buffer[pos : pos + 2] = int(value).to_bytes(2, "little")
    return pos + 2


def _uint32_from_buffer(buffer: bytes, pos: int) -> int:
    """Decode a uint32."""
    return int.from_bytes(buffer[pos : pos + 4], "little")


def _uint32_to_buffer(buffer: bytearray, pos: int, value: int) -> int:
    """Encode a uint32."""
    buffer[pos : pos + 4] = int(value).to_bytes(4, "little")
    return pos + 4


def _calories_from_buffer(buffer: bytes, pos: int) -> float:
    """Decode calories using the iFit scaling factor."""
    raw = int.from_bytes(buffer[pos : pos + 4], "little")
    return raw * 1024 / 100000000


def _calories_to_buffer(buffer: bytearray, pos: int, value: float) -> int:
    """Encode calories using the iFit scaling factor."""
    raw = int(value * 100000000 / 1024)
    buffer[pos : pos + 4] = raw.to_bytes(4, "little")
    return pos + 4


def _pulse_from_buffer(buffer: bytes, pos: int) -> dict[str, Any]:
    """Decode pulse data including source information."""
    pulse = buffer[pos]
    average = buffer[pos + 1]
    count = buffer[pos + 2]
    source = PulseSource(buffer[pos + 3])
    return {"pulse": pulse, "average": average, "count": count, "source": source}


def _pulse_to_buffer(buffer: bytearray, pos: int, value: Mapping[str, Any]) -> int:
    """Encode pulse data; only pulse and source are used."""
    pulse = int(value.get("pulse", 0))
    source = PulseSource(value.get("source", PulseSource.NO))
    buffer[pos] = pulse & 0xFF
    buffer[pos + 1] = 0
    buffer[pos + 2] = 0
    buffer[pos + 3] = int(source)
    return pos + 4


CONVERTERS = {
    "double": Converter(2, _double_from_buffer, _double_to_buffer),
    "boolean": Converter(1, _bool_from_buffer, _bool_to_buffer),
    "mode": Converter(1, _uint8_from_buffer, _uint8_to_buffer),
    "calories": Converter(4, _calories_from_buffer, _calories_to_buffer),
    "pulse": Converter(4, _pulse_from_buffer, _pulse_to_buffer),
    "one_byte_int": Converter(1, _uint8_from_buffer, _uint8_to_buffer),
    "two_bytes_int": Converter(2, _uint16_from_buffer, _uint16_to_buffer),
    "four_bytes_int": Converter(4, _uint32_from_buffer, _uint32_to_buffer),
}


CHARACTERISTICS = {
    "Kph": CharacteristicDefinition("Kph", 0, False, CONVERTERS["double"]),
    "Incline": CharacteristicDefinition("Incline", 1, False, CONVERTERS["double"]),
    "CurrentDistance": CharacteristicDefinition(
        "CurrentDistance", 4, True, CONVERTERS["four_bytes_int"]
    ),
    "Distance": CharacteristicDefinition("Distance", 6, True, CONVERTERS["four_bytes_int"]),
    "Volume": CharacteristicDefinition("Volume", 9, False, CONVERTERS["one_byte_int"]),
    "Pulse": CharacteristicDefinition("Pulse", 10, False, CONVERTERS["pulse"]),
    "UpTime": CharacteristicDefinition("UpTime", 11, True, CONVERTERS["four_bytes_int"]),
    "Mode": CharacteristicDefinition("Mode", 12, False, CONVERTERS["mode"]),
    "Calories": CharacteristicDefinition("Calories", 13, True, CONVERTERS["calories"]),
    "CurrentKph": CharacteristicDefinition("CurrentKph", 16, True, CONVERTERS["double"]),
    "CurrentIncline": CharacteristicDefinition(
        "CurrentIncline", 17, True, CONVERTERS["double"]
    ),
    "CurrentTime": CharacteristicDefinition(
        "CurrentTime", 20, True, CONVERTERS["four_bytes_int"]
    ),
    "CurrentCalories": CharacteristicDefinition(
        "CurrentCalories", 21, True, CONVERTERS["calories"]
    ),
    "MaxIncline": CharacteristicDefinition("MaxIncline", 27, True, CONVERTERS["double"]),
    "MinIncline": CharacteristicDefinition("MinIncline", 28, True, CONVERTERS["double"]),
    "MaxKph": CharacteristicDefinition("MaxKph", 30, True, CONVERTERS["double"]),
    "MinKph": CharacteristicDefinition("MinKph", 31, True, CONVERTERS["double"]),
    "Metric": CharacteristicDefinition("Metric", 36, False, CONVERTERS["boolean"]),
    "MaxPulse": CharacteristicDefinition("MaxPulse", 49, True, CONVERTERS["one_byte_int"]),
    "AverageIncline": CharacteristicDefinition(
        "AverageIncline", 52, True, CONVERTERS["double"]
    ),
    "TotalTime": CharacteristicDefinition("TotalTime", 70, True, CONVERTERS["four_bytes_int"]),
    "PausedTime": CharacteristicDefinition(
        "PausedTime", 103, True, CONVERTERS["four_bytes_int"]
    ),
    "X1": CharacteristicDefinition("X1", 34, False, CONVERTERS["two_bytes_int"]),
    "X2": CharacteristicDefinition("X2", 35, False, CONVERTERS["two_bytes_int"]),
    "X3": CharacteristicDefinition("X3", 43, False, CONVERTERS["double"]),
    "X4": CharacteristicDefinition("X4", 46, False, CONVERTERS["two_bytes_int"]),
    "X5": CharacteristicDefinition("X5", 69, False, CONVERTERS["four_bytes_int"]),
    "X6": CharacteristicDefinition("X6", 71, False, CONVERTERS["two_bytes_int"]),
    "X7": CharacteristicDefinition("X7", 100, False, CONVERTERS["one_byte_int"]),
}

CHARACTERISTICS_BY_ID = {value.id: value for value in CHARACTERISTICS.values()}

CAPABILITIES = {
    "Speed": CapabilityDefinition(65, 0),
    "Incline": CapabilityDefinition(66, 1),
    "Pulse": CapabilityDefinition(70, 10),
    "Key": CapabilityDefinition(71, 7),
    "Distance": CapabilityDefinition(77, 6),
    "Time": CapabilityDefinition(78, 11),
}

BLE_UUIDS = {
    "service": "000015331412efde1523785feabcd123",
    "rx": "000015351412efde1523785feabcd123",
    "tx": "000015341412efde1523785feabcd123",
}


def get_bitmap(
    equipment_information: EquipmentInformation,
    values: Iterable[CharacteristicDefinition | WriteValue] | None,
) -> bytearray:
    """Build a bitmap of characteristic ids used in a request."""
    payload = bytearray([0])
    if values is None:
        return payload

    for item in values:
        characteristic = (
            item.characteristic if isinstance(item, WriteValue) else item
        )
        # Only include characteristics supported by the connected equipment.
        if characteristic.id not in equipment_information.characteristics:
            continue
        pos = (characteristic.id // 8) + 1
        if pos > payload[0]:
            payload[0] = pos
            payload.extend([0] * (pos - len(payload) + 1))
        bit = characteristic.id - (pos - 1) * 8
        mask = 1 << bit
        payload[pos] |= mask

    for index in range(1, payload[0]):
        if index >= len(payload):
            payload.extend([0])
    return payload


def get_write_values(writes: Iterable[WriteValue] | None) -> bytearray | None:
    """Encode write values in ascending characteristic id order."""
    if not writes:
        return None

    writes_list = list(writes)
    size = 0
    for write in writes_list:
        converter = write.characteristic.converter
        size += converter.size if converter else 1

    payload = bytearray(size)
    pos = 0
    # iFit expects values ordered by characteristic id.
    for write in sorted(writes_list, key=lambda item: item.characteristic.id):
        converter = write.characteristic.converter
        if converter:
            pos = converter.to_buffer(payload, pos, write.value)
        else:
            payload[pos] = 0
            pos += 1
    return payload


def build_request(
    equipment: SportsEquipment | int,
    command: Command | int,
    payload: bytes | None = None,
) -> bytes:
    """Build the raw request payload for a command."""
    payload = payload or b""
    length = len(payload) + 4
    buf = bytearray(length + 4)

    checksum = int(equipment) + length + int(command)

    # Fixed header prefix used by iFit equipment.
    pos = 0
    buf[pos] = 2
    pos += 1
    buf[pos] = 4
    pos += 1
    buf[pos] = 2
    pos += 1
    buf[pos] = length
    pos += 1
    buf[pos] = int(equipment)
    pos += 1
    buf[pos] = length
    pos += 1
    buf[pos] = int(command)
    pos += 1
    for byte in payload:
        checksum += byte
        buf[pos] = byte
        pos += 1
    # Checksum is the low byte of the sum of header fields and payload bytes.
    buf[pos] = checksum & 0xFF
    return bytes(buf)


def request_header(request: bytes, number_of_writes: int) -> bytes:
    """Build the BLE header chunk for a framed request."""
    buf = bytearray(4)
    buf[0] = MessageIndex.HEADER
    buf[1] = 2
    buf[2] = len(request)
    buf[3] = number_of_writes + 1
    return bytes(buf)


def build_write_messages(request: bytes) -> list[bytes]:
    """Split a request into BLE chunks (header + payload fragments)."""
    number_of_writes = (len(request) + MAX_BYTES_PER_MESSAGE - 1) // MAX_BYTES_PER_MESSAGE
    messages = [request_header(request, number_of_writes)]

    offset = 0
    counter = 1
    done = offset == len(request)
    while not done:
        message = bytearray(20)
        length = (
            MAX_BYTES_PER_MESSAGE
            if counter < number_of_writes
            else ((len(request) - 1) % MAX_BYTES_PER_MESSAGE + 1)
        )
        # First byte is the chunk index (or EOF for the final chunk).
        message[0] = counter - 1
        message[1] = length
        message[2 : 2 + length] = request[offset : offset + length]

        offset += length
        done = offset == len(request)

        if done:
            message[0] = MessageIndex.EOF
        else:
            counter += 1
        messages.append(bytes(message))
    return messages


def determine_message_index(message: bytes) -> int:
    """Return the chunk index byte from a BLE message."""
    if len(message) < 1:
        raise ValueError(f"unexpected message format: {message.hex()}")
    return message[0]


def get_header_from_response(message: bytes) -> tuple[int, bytearray]:
    """Parse the response header chunk and return expected count + buffer."""
    if len(message) < 4:
        raise ValueError("unexpected message format - four bytes expected")
    if message[0] != MessageIndex.HEADER:
        raise ValueError(
            f"message is not a header: expected 0xfe got {message[0]}"
        )
    buf_length = message[2]
    upcoming_messages = message[3] - 1
    buffer = bytearray(buf_length)
    return upcoming_messages, buffer


def fill_response(buffer: bytearray, number_of_reads: int, message: bytes) -> None:
    """Copy a response chunk into the buffer based on its index."""
    if buffer is None:
        raise ValueError("undefined buffer")
    if len(message) < 2:
        raise ValueError("unexpected message format - two bytes expected")

    index = message[0]
    if index != MessageIndex.EOF and index >= number_of_reads:
        raise ValueError(
            f"index of message exceeds number of expected reads: {index}>={number_of_reads}"
        )

    # Map the chunk index to its offset in the full response buffer.
    pos = (number_of_reads - 1 if index == MessageIndex.EOF else index) * 18
    length = message[1]
    if length + pos > len(buffer):
        raise ValueError(
            f"amount of data in message exceeds buffer size: {length + pos}>{len(buffer)}"
        )
    buffer[pos : pos + length] = message[2 : 2 + length]


def parse_command_header(
    response: bytes, expected_command: Command | int
) -> dict[str, Any]:
    """Validate and parse the command response header."""
    if len(response) < 4:
        raise ValueError("unexpected buffer length - must be greater than 4 bytes")
    length = response[3]
    if len(response) != length + 4:
        raise ValueError(
            f"buffer length is {len(response)} but header says {length + 4} bytes"
        )

    pos = 4
    equipment = response[pos]
    pos += 1
    pos += 1
    command = response[pos]
    pos += 1
    if command != int(expected_command):
        raise ValueError(
            f"expected command {int(expected_command)} but got {command}"
        )
    status = response[pos]
    if status != RESPONSE_OK_CODE:
        raise ValueError(f"response code not OK: {status}")
    return {"equipment": equipment}


def parse_equipment_information_response(response: bytes) -> dict[int, CharacteristicDefinition]:
    """Parse equipment information and return supported characteristics."""
    pos = 16
    length = response[pos]
    pos += 1
    characteristics: dict[int, CharacteristicDefinition] = {}
    for offset in range(length):
        byte = response[pos]
        pos += 1
        for bit in range(8):
            mask = 1 << bit
            if byte & mask:
                char_id = offset * 8 + bit
                characteristic = CHARACTERISTICS_BY_ID.get(char_id)
                if characteristic:
                    characteristics[characteristic.id] = characteristic
    return characteristics


def parse_features_response(response: bytes) -> list[int]:
    """Parse a list of supported feature ids from a response."""
    if len(response) < 9:
        # Response too short, return empty list
        return []
    pos = 8
    count = response[pos]
    pos += 1
    
    # Validate we have enough data for all expected items
    if len(response) < pos + count:
        # Not enough data, return what we can parse
        count = len(response) - pos
    
    capabilities: list[int] = []
    for _ in range(count):
        capabilities.append(response[pos])
        pos += 1
    return capabilities


def parse_write_and_read_response(
    equipment_information: EquipmentInformation,
    response: bytes,
    reads: Iterable[CharacteristicDefinition],
) -> dict[str, Any]:
    """Parse read values from a write-and-read response."""
    result: dict[str, Any] = {}
    read_list = sorted(reads, key=lambda item: item.id)

    pos = 8
    for characteristic in read_list:
        if characteristic.id not in equipment_information.characteristics:
            continue
        converter = characteristic.converter
        if converter:
            result[characteristic.name] = converter.from_buffer(response, pos)
            pos += converter.size
    return result


def parse_equipment_firmware_response(response: bytes) -> str | None:
    """Parse firmware version from EQUIPMENT_FIRMWARE response.
    
    Structure:
    - Bytes 0-10: Header and metadata
    - Byte 11+: ASCII firmware version string
    
    Example: '0.1.06122017.0908'
    """
    if len(response) < 12:
        return None
    
    try:
        # Firmware string starts at byte 11
        firmware_bytes = response[11:]
        # Decode and stop at first control character (like \x01)
        firmware_str = firmware_bytes.decode('ascii', errors='ignore')
        # Split at control characters and take first part
        firmware_clean = firmware_str.split('\x01')[0].split('\x00')[0]
        return firmware_clean if firmware_clean else None
    except Exception:
        return None


def parse_equipment_reference_response(response: bytes) -> int | None:
    """Parse reference number from EQUIPMENT_REFERENCE response.
    
    Structure:
    - Bytes 0-14: Header and other data
    - Bytes 15-18: Reference number (little-endian 4-byte int)
    
    Example: 392748
    """
    if len(response) < 19:
        return None
    
    try:
        # Reference number is at bytes 15-18 (little-endian)
        reference = int.from_bytes(response[15:19], 'little')
        return reference
    except Exception:
        return None


def parse_equipment_serial_response(response: bytes) -> str | None:
    """Parse serial number from EQUIPMENT_SERIAL response.
    
    Structure:
    - Bytes 0-7: Header
    - Byte 8: Length of serial number string
    - Bytes 9-(9+length-1): Serial number (ASCII)
    - Last byte: Checksum
    
    Example: '392747-MM74Y102555'
    """
    if len(response) < 10:
        return None
    
    try:
        # Byte 8 contains the length of the serial number
        serial_length = response[8]
        
        # Serial number starts at byte 9
        if len(response) < 9 + serial_length:
            return None
            
        serial_bytes = response[9:9 + serial_length]
        serial_number = serial_bytes.decode('ascii', errors='ignore').strip()
        
        return serial_number if serial_number else None
    except Exception:
        return None
