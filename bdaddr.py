import asyncio

from bumble.device import Device
from bumble.hci import Address, HCI_Command, HCI_Reset_Command, hci_command_op_code


class BDAddrException(Exception):
    ...


async def bdaddr(device: Device, address: Address, reset: bool = False):
    if address.address_type != Address.PUBLIC_DEVICE_ADDRESS:
        raise BDAddrException("address should be PUBLIC_DEVICE_ADDRESS")
    local_version = device.host.local_version
    if local_version is None:
        raise BDAddrException("No available local_version")
    company_identifier: int
    company_identifier = local_version.company_identifier
    match company_identifier:
        case 0:
            await _ericsson_bdaddr(device, address)
        case 2:
            await _intel_bdaddr(device, address)
        case 10:
            await _csr_bdaddr(device, address)
        case 13:
            await _ti_bdaddr(device, address)
        case 15:
            await _bcm_bdaddr(device, address)
        case 18:
            await _zeevo_bdaddr(device, address)
        case 48:
            await _st_bdaddr(device, address)
        case 57:
            await _ericsson_bdaddr(device, address)
        case 305:
            await _cys_bdaddr(device, address)
        case _:
            raise BDAddrException("Unsupported manufacturer")
    if reset:
        match company_identifier:
            case 0:
                ...
            case 2:
                ...
            case 10:
                await _csr_reset(device)
            case 13:
                ...
            case 15:
                await device.host.send_command(HCI_Reset_Command(), check_result=True)
            case 18:
                ...
            case 48:
                await device.host.send_command(HCI_Reset_Command(), check_result=True)
            case 57:
                await device.host.send_command(HCI_Reset_Command(), check_result=True)
            case 305:
                ...
            case _:
                raise BDAddrException("Unsupported manufacturer")


def _hci_command(op_code, name=None, fields=[], return_parameters_fields=[]):
    def inner(cls):
        cls.name = name or cls.__name__.upper().strip("_")
        cls.op_code = op_code
        cls.fields = fields
        cls.return_parameters_fields = return_parameters_fields
        if fields is not None:

            def init(self, parameters=None, **kwargs):
                return HCI_Command.__init__(self, cls.op_code, parameters, **kwargs)

            cls.__init__ = init
        HCI_Command.command_classes[cls.op_code] = cls
        return cls

    return inner


async def _ericsson_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _Ericsson_Write_BDAddr_Command(address=address), check_result=True
    )


async def _intel_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _Intel_Write_BDAddr_Command(address=address), check_result=True
    )


async def _csr_bdaddr(device: Device, address: Address, transient: bool = False):
    # csr_write_pskey_complex
    payload = bytearray.fromhex("02000c001147037000000100040000000000000000000000")
    if transient:
        payload[14] = 0x08
    address_bytes = bytes(address)
    payload[16] = address_bytes[2]
    payload[17] = 0x00
    payload[18] = address_bytes[0]
    payload[19] = address_bytes[1]
    payload[20] = address_bytes[3]
    payload[21] = 0x00
    payload[22] = address_bytes[4]
    payload[23] = address_bytes[5]
    payload = bytes([0xC2]) + payload
    device.host.send_hci_packet(_CSR_Write_BDAddr_Command(payload=payload))
    await _csr_get_response(device)


async def _csr_reset(device: Device, transient: bool = False):
    payload = bytearray.fromhex("020009000000014000000000000000000000")
    if transient:
        payload[6] = 0x02
    payload = bytes([0xC2]) + payload
    device.host.send_hci_packet(_CSR_Write_BDAddr_Command(payload=payload))
    await _csr_get_response(device)


async def _csr_get_response(device: Device):
    future = asyncio.get_event_loop().create_future()
    origin_on_hci_event = device.host.on_hci_event
    try:

        def on_hci_event(event):
            if event.event_code == 0xFF:
                res = event.parameters
                if res[0] == 0xC2 and res[9] + res[10] << 8 == 0:
                    future.set_result(None)
                else:
                    future.set_exception(BDAddrException("Write BDAddr (CSR) failed"))
            else:
                origin_on_hci_event(event)

        device.host.on_hci_event = on_hci_event
    except:
        future.set_exception(BDAddrException("Some error occurred"))
    finally:
        device.host.on_hci_event = origin_on_hci_event
    return await future


async def _ti_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _TI_Write_BDAddr_Command(address=address), check_result=True
    )


async def _bcm_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _BCM_Write_BDAddr_Command(address=address), check_result=True
    )


async def _zeevo_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _Zeevo_Write_BDAddr_Command(address=address), check_result=True
    )


async def _st_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _Ericsson_Store_In_Flash_Command(user_id=0xFE, length=6, data=bytes(address)),
        check_result=True,
    )


async def _cys_bdaddr(device: Device, address: Address):
    await device.host.send_command(
        _CYS_Write_BDAddr_Command(address=address), check_result=True
    )


@_hci_command(
    hci_command_op_code(0x3F, 0x000D),
    fields=[("address", Address.parse_address)],
)
class _Ericsson_Write_BDAddr_Command(HCI_Command):
    ...


@_hci_command(
    hci_command_op_code(0x3F, 0x0022),
    fields=[
        ("user_id", 1),
        ("length", 1),
        ("data", 253),
    ],
)
class _Ericsson_Store_In_Flash_Command(HCI_Command):
    ...


@_hci_command(hci_command_op_code(0x3F, 0x0000), fields=[("payload", "*")])
class _CSR_Write_BDAddr_Command(HCI_Command):
    """use host.send_hci_packet and host.on_hci_event. maybe hci_event? no, it is hci_command."""


@_hci_command(
    hci_command_op_code(0x3F, 0x0006),
    fields=[("address", Address.parse_address)],
)
class _TI_Write_BDAddr_Command(HCI_Command):
    ...


@_hci_command(
    hci_command_op_code(0x3F, 0x0001),
    fields=[("address", Address.parse_address)],
)
class _BCM_Write_BDAddr_Command(HCI_Command):
    ...


@_hci_command(
    hci_command_op_code(0x3F, 0x0031),
    fields=[("address", Address.parse_address)],
)
class _Intel_Write_BDAddr_Command(HCI_Command):
    ...


@_hci_command(
    hci_command_op_code(0x3F, 0x0001),
    fields=[("address", Address.parse_address)],
)
class _CYS_Write_BDAddr_Command(HCI_Command):
    ...


@_hci_command(
    hci_command_op_code(0x3F, 0x0001),
    fields=[("address", Address.parse_address)],
)
class _Zeevo_Write_BDAddr_Command(HCI_Command):
    ...


if __name__ == "__main__":

    async def _main():
        import logging
        import sys

        from bumble.transport import open_transport_or_link

        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).setLevel("DEBUG")
        logging.getLogger("bumble").setLevel("DEBUG")
        logging.getLogger("bumble.transport").setLevel("INFO")

        transport = sys.argv[1]
        address = sys.argv[2]
        async with await open_transport_or_link(transport) as (hci_source, hci_sink):
            device = Device.with_hci(
                "Example Device", "F0:F0:F0:F0:F0:F0", hci_source, hci_sink
            )
            await device.power_on()
            await bdaddr(device, Address(address, Address.PUBLIC_DEVICE_ADDRESS))

    asyncio.run(_main())
