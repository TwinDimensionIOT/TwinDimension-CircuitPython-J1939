import adafruit_logging as logging
import board
import busio
import time
from digitalio import DigitalInOut
from adafruit_mcp2515.canio import Message, RemoteTransmissionRequest
from adafruit_mcp2515 import MCP2515 as CAN

logger = logging.getLogger("can")

class CanBus:
    """
    """

    def __init__(self, **kwargs):
        """
        """
        print(kwargs);
        self._bus_type = kwargs.get('bus_type')
        logger.info("bus_type {0}".format(self._bus_type))
        if self._bus_type == "native":
            # ToDo
            pass
        elif self._bus_type == "mcp2515":
            self._cs = DigitalInOut(kwargs.get('cs'))
            self._cs.switch_to_output()
            self._spi = busio.SPI(kwargs.get('sck'), kwargs.get('mosi'), kwargs.get('miso'))
            self._bus = CAN(self._spi, self._cs, debug = True)
        self._on_receive = kwargs.get('on_receive')

    def shutdown(self):
        """Shutdown the CAN bus.
        """
        logger.info("shutdown | bus_type {0}".format(self._bus_type))
        if self._bus_type == "native":
            # ToDo
            pass
        elif self._bus_type == "mcp2515":        
            self._bus.deinit();
        self._bus = None
        self._notify = None

    def send(self, can_id, data, extended_id):
        """Send a raw CAN message to the bus.
        """
        logger.debug("send | bus_type {0} | can_id {1} | extended_id {2} | data {3}".format(self._bus_type, can_id, extended_id, data))
        if not self._bus:
            raise RuntimeError("Not connected to CAN bus")
        if self._bus_type == "native":
            # ToDo
            pass
        elif self._bus_type == "mcp2515":
            message = Message(can_id, data, extended_id)
            self._bus.send(message)

    def loop(self, timeout=0.1):
        timestamp = time.time()
        with self._bus.listen(timeout = timeout) as listener:
            message_count = listener.in_waiting()
            while message_count > 0: 
                for _i in range(message_count):
                    msg = listener.receive()
                    if self._on_receive:
                        self._on_receive(msg.id, msg.data, timestamp)
                message_count -= 1