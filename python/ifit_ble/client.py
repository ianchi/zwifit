from __future__ import annotations

import asyncio
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Iterable

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
    parse_equipment_reference_response,
    parse_equipment_firmware_response,
    parse_equipment_serial_response,
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
        response_timeout: float = 10.0,
    ) -> None:
        """Create a client bound to a BLE device address.
        
        Args:
            address: BLE MAC address of the device
            activation_code: 8-byte hex activation code (optional - enables control if provided)
            model: Model name for hardcoded initialization (optional if activation_code is provided)
            response_timeout: Timeout for responses in seconds
        
        Notes:
            - No activation_code/model: Monitor-only mode (NongoFit-style read-only, no discovery)
            - With activation_code only: Discovery + control mode (commands 81-95 + 90)
            - With model only: Uses hardcoded initialization sequences
            - With both: Invalid (cannot specify both activation_code and model)
        """
        if activation_code is not None and model is not None:
            raise ValueError("Cannot specify both activation_code and model")
        if model is not None and model not in INIT_SEQUENCES:
            raise ValueError(f"Model '{model}' not found in INIT_SEQUENCES")
        
        self.address = address
        self.activation_code = activation_code
        self.model = model
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

    async def try_activation_codes(
        self,
        codes_file: str | Path | None = None,
        max_attempts: int | None = None,
    ) -> tuple[str, str]:
        """Try all activation codes until one successfully activates the equipment.
        
        This method connects to the device and attempts activation with each code
        from the codes file until one succeeds. The device remains connected after
        successful activation.
        
        Args:
            codes_file: Path to CSV file with activation codes. If None, uses
                       codes_reverse.csv in the same directory as this module.
            max_attempts: Maximum number of codes to try. If None, tries all codes.
        
        Returns:
            Tuple of (successful_activation_code, model_name)
        
        Raises:
            ValueError: If no activation code works
            FileNotFoundError: If codes file doesn't exist
            
        Example:
            >>> client = IFitBleClient("AA:BB:CC:DD:EE:FF")
            >>> code, model = await client.try_activation_codes()
            >>> print(f"Activated with {model}: {code}")
        """
        # Load activation codes from CSV
        if codes_file is None:
            # Default to codes_reverse.csv in the python directory
            module_dir = Path(__file__).parent.parent
            codes_file = module_dir / "codes_reverse.csv"
        
        codes_file = Path(codes_file)
        if not codes_file.exists():
            raise FileNotFoundError(f"Activation codes file not found: {codes_file}")
        
        activation_codes: list[tuple[str, str]] = []
        with open(codes_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    # Use the full activation code from CSV (variable length)
                    code = row[0].strip()
                    # Handle multiple model names separated by semicolon
                    model = row[1].strip().split(";")[0]
                    activation_codes.append((code, model))
        
        if not activation_codes:
            raise ValueError(f"No activation codes found in {codes_file}")
        
        LOGGER.info(f"Loaded {len(activation_codes)} activation codes from {codes_file}")
        
        # Limit attempts if specified
        codes_to_try = activation_codes[:max_attempts] if max_attempts else activation_codes
        
        # Connect to device if not already connected
        if not self._client.is_connected:
            await self.connect()
        
        # Try each activation code
        for i, (code, model) in enumerate(codes_to_try, 1):
            LOGGER.info(f"Trying activation code {i}/{len(codes_to_try)}: {model}")
            
            try:
                # Temporarily set the activation code
                self.activation_code = code
                
                # Try to enable equipment with this code
                await self._enable_equipment()
                
                # Verify activation by trying to read a characteristic
                # If the code is wrong, this will likely fail or timeout
                try:
                    await asyncio.wait_for(
                        self.read_characteristics(["MaxIncline", "MinIncline"]),
                        timeout=2.0
                    )
                    # Success! The code worked
                    LOGGER.info(f"✓ Activation successful with code for {model}")
                    return code, model
                    
                except (asyncio.TimeoutError, Exception) as e:
                    LOGGER.debug(f"Code verification failed for {model}: {e}")
                    continue
                    
            except Exception as e:
                LOGGER.debug(f"Activation failed for {model}: {e}")
                continue
        
        # If we get here, no code worked
        self.activation_code = None
        raise ValueError(
            f"Failed to activate equipment. Tried {len(codes_to_try)} codes with no success. "
            "The device may not be supported or may require a different activation method."
        )

    async def connect(self) -> None:
        """Connect to the BLE device and initialize protocol state."""
        await self._client.connect()
        
        # Wait for services to stabilize after connection (device may reconfigure)
        await asyncio.sleep(0.6)
        
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
        await asyncio.sleep(0.6)
        await self._initialize_equipment()

    async def disconnect(self) -> None:
        """Disconnect and stop notifications."""
        if self._client.is_connected:
            await self._client.stop_notify(BLE_UUIDS["rx"])
            await self._client.disconnect()

    async def _initialize_equipment(self) -> None:
        """Load equipment metadata and discover capabilities.
        
        Runs the standard discovery sequence:
        - 81: EQUIPMENT_INFORMATION
        - 80: SUPPORTED_CAPABILITIES
        - 88: SUPPORTED_COMMANDS
        - 82: EQUIPMENT_REFERENCE
        - 84: EQUIPMENT_FIRMWARE
        - 95: EQUIPMENT_SERIAL
        """

        # Use hardcoded sequence if model is specified
        if self.model is not None:
            await self._initialize_with_hardcoded_sequence()
            return
        
        # Standard initialization sequence
        # Command 81: EQUIPMENT_INFORMATION
        header, response = await self._send_command(Command.EQUIPMENT_INFORMATION)
        characteristics = parse_equipment_information_response(response)
        equipment_info = EquipmentInformation(
            equipment=SportsEquipment(header["equipment"]),
            characteristics=characteristics,
        )
        
        # Store equipment information
        self._equipment_information = equipment_info
        
        # Command 80: SUPPORTED_CAPABILITIES
        _, response = await self._send_command(Command.SUPPORTED_CAPABILITIES)
        equipment_info.supported_capabilities = parse_features_response(response)
        
        # Command 88: SUPPORTED_COMMANDS - get list of supported commands
        try:
            _, response = await self._send_command(Command.SUPPORTED_COMMANDS)
            equipment_info.supported_commands = parse_features_response(response)
            LOGGER.debug(f"Supported commands: {equipment_info.supported_commands}")
        except Exception as e:
            LOGGER.warning(f"Could not get supported commands: {e}")
        
        # Query additional equipment information commands if supported
        for cmd in [Command.EQUIPMENT_REFERENCE, Command.EQUIPMENT_FIRMWARE, Command.EQUIPMENT_SERIAL]:
            if cmd in equipment_info.supported_commands:
                try:
                    _, response = await self._send_command(cmd, b"\x00\x00")
                    LOGGER.debug(f"{cmd.name}: {response.hex()}")
                    
                    # Parse reference number
                    if cmd == Command.EQUIPMENT_REFERENCE:
                        reference = parse_equipment_reference_response(response)
                        if reference:
                            equipment_info.reference_number = reference
                            LOGGER.info(f"Reference number: {reference}")
                    
                    # Parse firmware version
                    elif cmd == Command.EQUIPMENT_FIRMWARE:
                        firmware = parse_equipment_firmware_response(response)
                        if firmware:
                            equipment_info.firmware_version = firmware
                            LOGGER.info(f"Firmware version: {firmware}")
                    
                    # Parse serial number
                    elif cmd == Command.EQUIPMENT_SERIAL:
                        serial = parse_equipment_serial_response(response)
                        if serial:
                            equipment_info.serial_number = serial
                            LOGGER.info(f"Serial number: {serial}")
                    
                except Exception as e:
                    LOGGER.warning(f"Could not get {cmd.name}: {e}")
            else:
                LOGGER.debug(f"Command {cmd.name} not supported, skipping")
        

        
        # Enable equipment with activation code if provided
        if self.activation_code is not None:
            await self._enable_equipment()
            
            # Read min/max values after enabling
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
            header, response = await self._send_command(Command.EQUIPMENT_INFORMATION)
            characteristics = parse_equipment_information_response(response)
            self._equipment_information = EquipmentInformation(
                equipment=SportsEquipment(header["equipment"]),
                characteristics=characteristics,
            )
            
            # Try to get serial and firmware if available
            try:
                _, response = await self._send_command(Command.EQUIPMENT_REFERENCE, b"\x00\x00")
                reference = parse_equipment_reference_response(response)
                if reference:
                    self._equipment_information.reference_number = reference
                    LOGGER.info(f"Reference number: {reference}")
            except Exception:
                pass
            
            try:
                _, response = await self._send_command(Command.EQUIPMENT_FIRMWARE, b"\x00\x00")
                firmware = parse_equipment_firmware_response(response)
                if firmware:
                    self._equipment_information.firmware_version = firmware
                    LOGGER.info(f"Firmware version: {firmware}")
            except Exception:
                pass
            
            try:
                _, response = await self._send_command(Command.EQUIPMENT_SERIAL, b"\x00\x00")
                serial = parse_equipment_serial_response(response)
                if serial:
                    self._equipment_information.serial_number = serial
                    LOGGER.info(f"Serial number: {serial}")
            except Exception:
                pass
                
        except Exception as e:
            LOGGER.warning(f"Could not get equipment info after hardcoded init: {e}")
            # Create a minimal equipment info object
            self._equipment_information = EquipmentInformation(
                equipment=SportsEquipment.GENERAL,
                characteristics=[],
            )

    async def _send_command(
        self,
        command: Command,
        payload: bytes = b"",
    ) -> tuple[dict[str, Any], bytes]:
        """Send a command and return the parsed header and raw response.
        
        Args:
            command: Command to send
            payload: Optional payload bytes
            equipment: Equipment type (defaults to GENERAL or current equipment info)
        
        Returns:
            Tuple of (parsed header dict, raw response bytes)
        """
        equipment_value = self._equipment_information.equipment if self._equipment_information else SportsEquipment.GENERAL
        request = build_request(equipment_value, command, payload)
        response = await self._send_request(request)
        header = parse_command_header(response, command)
        return header, response

    async def _enable_equipment(self) -> None:
        """Send the activation code so reads/writes are accepted."""
        if self.activation_code is None:
            raise ValueError("activation_code is required for standard initialization")
        payload = bytes.fromhex(self.activation_code)
        _, response = await self._send_command(Command.ENABLE, payload)
        LOGGER.debug(f"Enable response: {response.hex()}")

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

        _, response = await self._send_command(Command.WRITE_AND_READ, payload)
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
    
    async def set_speed(self, kph: float) -> None:
        """Set the treadmill speed in km/h.
        
        Args:
            kph: Speed in kilometers per hour
        """
        await self.write_characteristics({"Kph": kph})
    
    async def set_incline(self, percent: float) -> None:
        """Set the treadmill incline in percent.
        
        Args:
            percent: Incline percentage
        """
        await self.write_characteristics({"Incline": percent})
    
    async def monitor_basic_state(self) -> AsyncGenerator[dict[str, Any], None]:
        """Read basic monitoring values in a loop."""
        
        for _ in range(5):  # Example: read 5 times
            result = await self.read_current_values()
            yield result

            await asyncio.sleep(5.0)  # Wait 5 seconds between reads
        

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

    async def calibrate_incline(self) -> None:
        """Request incline calibration on the treadmill."""
        await self._send_command(Command.CALIBRATE, b"\x00")

    async def _send_request(self, request: bytes) -> bytes:
        """Send a raw request and wait for the response."""
        async with self._response_lock:
            loop = asyncio.get_running_loop()
            self._response_future = loop.create_future()
            self._response_state = _ResponseState()

            # Write the request as BLE chunks; response will arrive via notify.
            for message in build_write_messages(request):
                print(message.hex())
                await self._client.write_gatt_char(BLE_UUIDS["tx"], message, response=False)
                await asyncio.sleep(0.2)  # Throttle writes to avoid overwhelming device

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

    def _require_equipment_info(self) -> EquipmentInformation:
        """Return equipment info or raise if not available."""
        if self._equipment_information is None:
            raise ValueError("Equipment information not available. Call connect() first.")
        return self._equipment_information

    def _coerce_characteristic(self, item: str | int) -> CharacteristicDefinition:
        """Convert a characteristic name or id to a CharacteristicDefinition."""
        if isinstance(item, int):
            if item not in CHARACTERISTICS_BY_ID:
                raise ValueError(f"Unknown characteristic id: {item}")
            return CHARACTERISTICS_BY_ID[item]
        if item not in CHARACTERISTICS:
            raise ValueError(f"Unknown characteristic name: {item}")
        return CHARACTERISTICS[item]

    @staticmethod
    def _validate_checksum(response: bytes) -> None:
        """Validate the response checksum; raises on mismatch."""
        if len(response) <= 5:
            return
        checksum = sum(response[4:-1]) & 0xFF
        if checksum != response[-1]:
            raise ValueError("checksum invalid")
