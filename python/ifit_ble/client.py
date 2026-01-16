from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

from bleak import BleakClient

from .protocol import (
    BLE_UUIDS,
    CHARACTERISTICS,
    CHARACTERISTICS_BY_ID,
    Command,
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


@dataclass
class _ResponseState:
    upcoming_messages: int = -1
    buffer: bytearray | None = None


class IFitBleClient:
    def __init__(
        self,
        address: str,
        activation_code: str,
        *,
        response_timeout: float = 10.0,
    ) -> None:
        self.address = address
        self.activation_code = activation_code
        self.response_timeout = response_timeout
        self._client = BleakClient(address)
        self._equipment_information: EquipmentInformation | None = None
        self._response_lock = asyncio.Lock()
        self._response_future: asyncio.Future[bytes] | None = None
        self._response_state = _ResponseState()

    @property
    def equipment_information(self) -> EquipmentInformation | None:
        return self._equipment_information

    async def connect(self) -> None:
        await self._client.connect()
        await self._client.start_notify(BLE_UUIDS["rx"], self._handle_notify)
        await self._initialize_equipment()

    async def disconnect(self) -> None:
        if self._client.is_connected:
            await self._client.stop_notify(BLE_UUIDS["rx"])
            await self._client.disconnect()

    async def _initialize_equipment(self) -> None:
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

    async def _get_equipment_information(self) -> EquipmentInformation:
        request = build_request(SportsEquipment.GENERAL, Command.EQUIPMENT_INFORMATION)
        response = await self._send_request(request)
        header = parse_command_header(response, Command.EQUIPMENT_INFORMATION)
        characteristics = parse_equipment_information_response(response)
        return EquipmentInformation(
            equipment=SportsEquipment(header["equipment"]),
            characteristics=characteristics,
        )

    async def _get_supported_capabilities(self, info: EquipmentInformation) -> list[int]:
        request = build_request(info.equipment, Command.SUPPORTED_CAPABILITIES)
        response = await self._send_request(request)
        parse_command_header(response, Command.SUPPORTED_CAPABILITIES)
        return parse_features_response(response)

    async def _enable_equipment(self, info: EquipmentInformation) -> None:
        payload = bytes.fromhex(self.activation_code)
        request = build_request(info.equipment, Command.ENABLE, payload)
        response = await self._send_request(request)
        parse_command_header(response, Command.ENABLE)

    async def write_and_read(
        self,
        writes: Iterable[WriteValue] | None,
        reads: Iterable[str | int],
    ) -> dict[str, Any]:
        info = self._require_equipment_info()
        write_values = list(writes) if writes else []
        read_defs = [self._coerce_characteristic(item) for item in reads]

        write_payload = get_bitmap(info, write_values)
        read_payload = get_bitmap(info, read_defs)
        write_value_payload = get_write_values(write_values)

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
        return await self.write_and_read(None, reads)

    async def write_characteristics(self, values: dict[str, Any]) -> None:
        writes = [WriteValue(self._coerce_characteristic(key), value) for key, value in values.items()]
        await self.write_and_read(writes, [])

    async def read_current_values(self) -> dict[str, Any]:
        return await self.read_characteristics(
            ["Kph", "CurrentKph", "CurrentIncline", "Pulse", "Mode"]
        )

    def _coerce_characteristic(self, item: str | int) -> Any:
        if isinstance(item, str):
            return CHARACTERISTICS[item]
        characteristic = CHARACTERISTICS_BY_ID.get(item)
        if characteristic is None:
            raise KeyError(f"Unknown characteristic id: {item}")
        return characteristic

    def _require_equipment_info(self) -> EquipmentInformation:
        if not self._equipment_information:
            raise RuntimeError("Equipment information not initialized")
        return self._equipment_information

    async def _send_request(self, request: bytes) -> bytes:
        async with self._response_lock:
            loop = asyncio.get_running_loop()
            self._response_future = loop.create_future()
            self._response_state = _ResponseState()

            for message in build_write_messages(request):
                await self._client.write_gatt_char(BLE_UUIDS["tx"], message, response=False)

            response = await asyncio.wait_for(self._response_future, timeout=self.response_timeout)
            return response

    def _handle_notify(self, _: int, data: bytearray) -> None:
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
        if len(response) <= 5:
            return
        checksum = sum(response[4:-1]) & 0xFF
        if checksum != response[-1]:
            raise ValueError("checksum invalid")
