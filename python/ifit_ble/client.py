from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from bleak import BleakClient

from .protocol import (
    BLE_UUIDS,
    CAPABILITIES,
    CHARACTERISTICS,
    CHARACTERISTICS_BY_ID,
    Command,
    CharacteristicDefinition,
    EquipmentInformation,
    MessageIndex,
    SportsEquipment,
    WriteValue,
    build_request,
    build_write_messages,
    determine_message_index,
    fill_response,
    get_bitmap,
    get_header_from_response,
    get_write_values,
    parse_command_header,
    parse_equipment_information_response,
    parse_features_response,
    parse_write_and_read_response,
)
from .hardcoded_init import INIT_SEQUENCES


LOGGER = logging.getLogger(__name__)


@dataclass
class _ResponseState:
    """Track in-flight response assembly state."""

    upcoming_messages: int = -1
    buffer: bytearray | None = None


class IFitBleClient:
    """BLE client for iFit equipment implementing the custom protocol."""

    def __init__(
        self,
        address: str,
        activation_code: str | None = None,
        *,
        model: str | None = None,
        monitor_only: bool = False,
        response_timeout: float = 10.0,
    ) -> None:
        """Create a client bound to a BLE device address.
        
        Args:
            address: BLE MAC address of the device
            activation_code: 8-byte hex activation code (optional if model or monitor_only is provided)
            model: Model name for hardcoded initialization (optional if activation_code is provided)
            monitor_only: If True, only monitor state without authentication (no control)
            response_timeout: Timeout for responses in seconds
        """
        if not monitor_only and activation_code is None and model is None:
            raise ValueError("Either activation_code, model, or monitor_only=True must be provided")
        if activation_code is not None and model is not None:
            raise ValueError("Cannot specify both activation_code and model")
        if monitor_only and (activation_code is not None or model is not None):
            raise ValueError("monitor_only cannot be used with activation_code or model")
        if model is not None and model not in INIT_SEQUENCES:
            raise ValueError(f"Model '{model}' not found in INIT_SEQUENCES")
        
        self.address = address
        self.activation_code = activation_code
        self.model = model
        self.monitor_only = monitor_only
        self.response_timeout = response_timeout
        self._client = BleakClient(address)
        self._equipment_information: EquipmentInformation | None = None
        self._response_lock = asyncio.Lock()
        self._response_future: asyncio.Future[bytes] | None = None
        self._response_state = _ResponseState()

    @property
    def equipment_information(self) -> EquipmentInformation | None:
        """Return cached equipment information when available."""
        return self._equipment_information

    async def connect(self) -> None:
        """Connect to the BLE device and initialize protocol state."""
        await self._client.connect()
        
        # Wait for services to stabilize after connection (device may reconfigure)
        await asyncio.sleep(1.0)
        
        # Re-discover services after potential reconfiguration
        services = self._client.services
        
        # validate the equipment is a valid iFit device by checking uuid
        required_uuids = {BLE_UUIDS["rx"], BLE_UUIDS["tx"]}
        # Normalize UUIDs by removing hyphens for comparison
        available_uuids = {char.uuid.replace("-", "") for service in services for char in service.characteristics}
        
        if not required_uuids.issubset(available_uuids):
            missing = required_uuids - available_uuids
            await self._client.disconnect()
            raise ValueError(f"Device is not a valid iFit device. Missing UUIDs: {missing}")
        
        await self._client.start_notify(BLE_UUIDS["rx"], self._handle_notify)
        await self._initialize_equipment()

    async def disconnect(self) -> None:
        """Disconnect and stop notifications."""
        if self._client.is_connected:
            await self._client.stop_notify(BLE_UUIDS["rx"])
            await self._client.disconnect()

    async def _initialize_equipment(self) -> None:
        """Load equipment metadata and default capability values."""
        # Use monitor-only mode if specified (NongoFit approach)
        if self.monitor_only:
            await self._initialize_monitor_only()
            return
        
        # Use hardcoded sequence if model is specified
        if self.model is not None:
            await self._initialize_with_hardcoded_sequence()
            return
        
        # Otherwise use standard initialization with activation code
        equipment_info = await self._get_equipment_information()
        supported = await self._get_supported_capabilities(equipment_info)
        equipment_info.supported_capabilities = supported
        await self._enable_equipment(equipment_info)
        max_min = await self.read_characteristics(
            [
                "MaxIncline",
                "MinIncline",
                "MaxKph",
                "MinKph",
                "MaxPulse",
                "Metric",
            ]
        )
        equipment_info.values.update(max_min)
        self._equipment_information = equipment_info
    
    async def _initialize_with_hardcoded_sequence(self) -> None:
        """Initialize using hardcoded byte sequences for this model."""
        LOGGER.info(f"Initializing with hardcoded sequence for model: {self.model}")
        
        sequences = INIT_SEQUENCES[self.model]
        for i, sequence in enumerate(sequences, 1):
            LOGGER.debug(f"Sending sequence {i}/{len(sequences)}: {sequence.hex()}")
            await self._client.write_gatt_char(BLE_UUIDS["tx"], sequence, response=False)
            await asyncio.sleep(0.3)
        
        LOGGER.info("Hardcoded sequence initialization complete")
        
        # Try to get equipment information for metadata
        # This may or may not work depending on the sequence
        try:
            equipment_info = await self._get_equipment_information()
            self._equipment_information = equipment_info
        except Exception as e:
            LOGGER.warning(f"Could not get equipment info after hardcoded init: {e}")
            # Create a minimal equipment info object
            self._equipment_information = EquipmentInformation(
                equipment=SportsEquipment.GENERAL,
                characteristics=[],
            )
    
    async def _initialize_monitor_only(self) -> None:
        """Initialize in monitor-only mode (NongoFit approach - no activation needed)."""
        LOGGER.info("Initializing in monitor-only mode (no activation required)")
        
        # Create minimal equipment info for TREADMILL
        # In monitor mode, we don't query capabilities - just assume basic characteristics exist
        self._equipment_information = EquipmentInformation(
            equipment=SportsEquipment.TREADMILL,
            characteristics={
                0: CHARACTERISTICS["Kph"],
                1: CHARACTERISTICS["Incline"],
                4: CHARACTERISTICS["CurrentDistance"],
                10: CHARACTERISTICS["Pulse"],
                12: CHARACTERISTICS["Mode"],
                16: CHARACTERISTICS["CurrentKph"],
                17: CHARACTERISTICS["CurrentIncline"],
                20: CHARACTERISTICS["CurrentTime"],
            },
        )
        
        LOGGER.info("Monitor-only mode initialized (read-only access)")

    async def _get_equipment_information(self) -> EquipmentInformation:
        """Request and parse the core equipment information payload."""
        request = build_request(SportsEquipment.GENERAL, Command.EQUIPMENT_INFORMATION)
        response = await self._send_request(request)
        header = parse_command_header(response, Command.EQUIPMENT_INFORMATION)
        characteristics = parse_equipment_information_response(response)
        return EquipmentInformation(
            equipment=SportsEquipment(header["equipment"]),
            characteristics=characteristics,
        )

    async def _get_supported_capabilities(self, info: EquipmentInformation) -> list[int]:
        """Request supported capability ids for the given equipment."""
        request = build_request(info.equipment, Command.SUPPORTED_CAPABILITIES)
        response = await self._send_request(request)
        parse_command_header(response, Command.SUPPORTED_CAPABILITIES)
        return parse_features_response(response)

    async def _enable_equipment(self, info: EquipmentInformation) -> None:
        """Send the activation code so reads/writes are accepted."""
        if self.activation_code is None:
            raise ValueError("activation_code is required for standard initialization")
        payload = bytes.fromhex(self.activation_code)
        request = build_request(info.equipment, Command.ENABLE, payload)
        response = await self._send_request(request)
        parse_command_header(response, Command.ENABLE)

    async def write_and_read(
        self,
        writes: Iterable[WriteValue] | None,
        reads: Iterable[str | int],
    ) -> dict[str, Any]:
        """Write characteristics and return requested read values."""
        info = self._require_equipment_info()
        write_values = list(writes) if writes else []
        read_defs = [self._coerce_characteristic(item) for item in reads]

        write_payload = get_bitmap(info, write_values)
        read_payload = get_bitmap(info, read_defs)
        write_value_payload = get_write_values(write_values)

        # Payload layout: write bitmap, write values, read bitmap.
        payload_parts = [write_payload]
        if write_value_payload:
            payload_parts.append(write_value_payload)
        payload_parts.append(read_payload)
        payload = b"".join(payload_parts)

        request = build_request(info.equipment, Command.WRITE_AND_READ, payload)
        response = await self._send_request(request)
        parse_command_header(response, Command.WRITE_AND_READ)
        return parse_write_and_read_response(info, response, read_defs)

    async def read_characteristics(self, reads: Iterable[str | int]) -> dict[str, Any]:
        """Read characteristic values by name or id."""
        return await self.write_and_read(None, reads)

    async def write_characteristics(self, values: dict[str, Any]) -> None:
        """Write characteristic values by name."""
        writes = [
            WriteValue(self._coerce_characteristic(key), value)
            for key, value in values.items()
        ]
        await self.write_and_read(writes, [])

    async def read_current_values(self) -> dict[str, Any]:
        """Read commonly updated values from the treadmill."""
        return await self.read_characteristics(
            ["Kph", "CurrentKph", "CurrentIncline", "Pulse", "Mode"]
        )
    
    async def monitor_basic_state(self) -> dict[str, Any]:
        """Read basic monitoring values (NongoFit-compatible).
        
        Returns the 5 basic values that NongoFit monitors:
        - pace (Kph converted to mph if needed)
        - incline (percentage)
        - distance (CurrentDistance)
        - pulse (heart rate)
        - timer (CurrentTime in seconds)
        
        This works in both monitor_only mode and full mode.
        """
        values = await self.read_characteristics(
            ["Kph", "Incline", "CurrentDistance", "Pulse", "CurrentTime"]
        )
        
        # Format similar to NongoFit's output
        result = {
            "pace": values.get("Kph", 0.0),  # kph (convert to mph if needed)
            "incline": values.get("Incline", 0.0),  # percentage
            "distance": values.get("CurrentDistance", 0),  # meters or similar
            "pulse": values.get("Pulse", {}).get("pulse", 0) if isinstance(values.get("Pulse"), dict) else 0,
            "timer": values.get("CurrentTime", 0),  # seconds
        }
        
        return result

    async def get_supported_commands(
        self, equipment: SportsEquipment | None = None
    ) -> list[int]:
        """Return supported command ids for the given equipment."""
        equipment_value = equipment or self._require_equipment_info().equipment
        request = build_request(equipment_value, Command.SUPPORTED_COMMANDS)
        response = await self._send_request(request)
        parse_command_header(response, Command.SUPPORTED_COMMANDS)
        return parse_features_response(response)

    async def get_equipment_information2(self) -> bytes:
        """Fetch additional equipment information response bytes."""
        request = build_request(
            SportsEquipment.GENERAL, Command.EQUIPMENT_INFORMATION2, b"\x00\x00"
        )
        response = await self._send_request(request)
        parse_command_header(response, Command.EQUIPMENT_INFORMATION2)
        return response

    async def get_equipment_information3(self) -> bytes:
        """Fetch additional equipment information response bytes."""
        request = build_request(
            SportsEquipment.GENERAL, Command.EQUIPMENT_INFORMATION3, b"\x00\x00"
        )
        response = await self._send_request(request)
        parse_command_header(response, Command.EQUIPMENT_INFORMATION3)
        return response

    async def get_equipment_information4(self) -> bytes:
        """Fetch additional equipment information response bytes."""
        request = build_request(
            SportsEquipment.GENERAL, Command.EQUIPMENT_INFORMATION4, b"\x00\x00"
        )
        response = await self._send_request(request)
        parse_command_header(response, Command.EQUIPMENT_INFORMATION4)
        return response

    async def calibrate_incline(self) -> None:
        """Request incline calibration on the treadmill."""
        request = build_request(CAPABILITIES["Incline"].id, Command.CALIBRATE, b"\x00")
        response = await self._send_request(request)
        parse_command_header(response, Command.CALIBRATE)

    def _coerce_characteristic(self, item: str | int) -> CharacteristicDefinition:
        """Resolve a characteristic by name or numeric id."""
        if isinstance(item, str):
            return CHARACTERISTICS[item]
        characteristic = CHARACTERISTICS_BY_ID.get(item)
        if characteristic is None:
            raise KeyError(f"Unknown characteristic id: {item}")
        return characteristic

    def _require_equipment_info(self) -> EquipmentInformation:
        """Return equipment info or raise if not initialized."""
        if not self._equipment_information:
            raise RuntimeError("Equipment information not initialized")
        return self._equipment_information

    async def _send_request(self, request: bytes) -> bytes:
        """Send a framed request and await its full response."""
        async with self._response_lock:
            loop = asyncio.get_running_loop()
            self._response_future = loop.create_future()
            self._response_state = _ResponseState()

            # Write the request as BLE chunks; response will arrive via notify.
            for message in build_write_messages(request):
                print(message.hex())
                await self._client.write_gatt_char(BLE_UUIDS["tx"], message, response=False)

            response = await asyncio.wait_for(self._response_future, timeout=self.response_timeout)
            return response

    def _handle_notify(self, _: int, data: bytearray) -> None:
        """Assemble response chunks from BLE notifications."""
        if not self._response_future or self._response_future.done():
            return

        try:
            message_index = determine_message_index(data)
            if message_index == MessageIndex.HEADER:
                upcoming_messages, buffer = get_header_from_response(bytes(data))
                self._response_state.upcoming_messages = upcoming_messages
                self._response_state.buffer = buffer
                return

            if not self._response_state.buffer:
                raise ValueError("response buffer not initialized")

            # Merge the chunk into the response buffer using the index in byte 0.
            fill_response(
                self._response_state.buffer,
                self._response_state.upcoming_messages,
                bytes(data),
            )

            if message_index == MessageIndex.EOF:
                response = bytes(self._response_state.buffer)
                self._validate_checksum(response)
                self._response_future.set_result(response)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._response_future.set_exception(exc)

    @staticmethod
    def _validate_checksum(response: bytes) -> None:
        """Validate the response checksum; raises on mismatch."""
        if len(response) <= 5:
            return
        checksum = sum(response[4:-1]) & 0xFF
        if checksum != response[-1]:
            raise ValueError("checksum invalid")
