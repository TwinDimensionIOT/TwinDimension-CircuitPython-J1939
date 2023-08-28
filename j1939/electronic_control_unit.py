import adafruit_logging as logging
import time
from .controller_application import ControllerApplication
from .parameter_group_number import ParameterGroupNumber
from .j1939_21 import J1939_21
from .j1939_22 import J1939_22
from .message_id import FrameFormat
from .can import CanBus

logger = logging.getLogger(__name__)

class ElectronicControlUnit:
    """ElectronicControlUnit (ECU) holding one or more ControllerApplications (CAs)."""

    def __init__(self, data_link_layer='j1939-21', max_cmdt_packets=1, minimum_tp_rts_cts_dt_interval=None, minimum_tp_bam_dt_interval=None, send_message=None):
        """
        :param data_link_layer:
            specify data-link-layer, 'j1939-21' or 'j1939-22'
        """
        if send_message:
            self.send_message = send_message

        self._bus = None

        if max_cmdt_packets > 0xFF:
            raise ValueError("max number of segments that can be sent is 0xFF")

        # set data link layer
        if data_link_layer == 'j1939-21':
            self.j1939_dll = J1939_21(self.send_message, self._notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, self._is_message_acceptable)
        elif data_link_layer == 'j1939-22':
            self.j1939_dll = J1939_22(self.send_message, self._notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, self._is_message_acceptable)
        else:
            raise ValueError("either 'j1939-21' or 'j1939-22' must be provided for data link layer")

        self._subscribers = []

        # List of timer events the loop should care of
        self._timer_events = []

    def stop(self):
        """Stops the ECU background handling

        This Function explicitely stops the background handling of the ECU.
        """
        pass

    def add_timer(self, delta_time, callback, cookie=None):
        """Adds a callback to the list of timer events

        :param delta_time:
            The time in seconds after which the event is to be triggered.
        :param callback:
            The callback function to call
        """

        d = {
            'delta_time': delta_time,
            'callback': callback,
            'deadline': (time.time() + delta_time),
            'cookie': cookie,
            }

        self._timer_events.append( d )

    def remove_timer(self, callback):
        """Removes ALL entries from the timer event list for the given callback

        :param callback:
            The callback to be removed from the timer event list
        """
        for event in self._timer_events:
            if event['callback'] == callback:
                self._timer_events.remove( event )

    def connect(self, **kwargs):
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str bustype:
            Name of the interface. See
            `python-can manual <https://python-can.readthedocs.io/en/latest/configuration.html#interface-names>`__
            for full list of supported interfaces.
        :param int bitrate:
            Bitrate in bit/s.

        :raises can.CanError:
            When connection fails.
        """
        logger.info("connect")
        self._bus = CanBus(**kwargs, on_receive = self.notify)
        #logger.info("Connected to '%s'", self._bus.channel_info)
        #self._notifier = can.Notifier(self._bus, self._listeners, 1)
        return self._bus

    def disconnect(self):
        """Disconnect from the CAN bus.

        Must be overridden in a subclass if a custom interface is used.
        """
        self._bus.shutdown()
        self._bus = None

    def subscribe(self, callback, device_address=None):
        """Add the given callback to the message notification stream.

        :param callback:
            Function to call when message is received.
        :param int device_address:
            Device address of the application.
            This is a simple way for peer-to-peer reception without adding a controller-application.
            Only one device address can be entered. Multiple device addresses are only possible with controller applications.
            Note: TP.CMDT will only be received if the destination address is bound to a controller application.
        """
        self._subscribers.append({'cb': callback, 'dev_adr':device_address})

    def unsubscribe(self, callback):
        """Stop listening for message.

        :param callback:
            Function to call when message is received.
        """
        for dic in self._subscribers:
            if dic['cb'] == callback:
                self._subscribers.remove(dic)


    def add_ca(self, **kwargs):
        """Add a ControllerApplication to the ECU.

        :param controller_application:
            A :class:`j1939.ControllerApplication` object.

        :param name:
            A :class:`j1939.Name` object.

        :param device_address:
            An integer representing the device address to announce to the bus.

        :return:
            The CA object that was added.

        :rtype: r3964.ControllerApplication
        """
        if 'controller_application' in kwargs:
            ca = kwargs['controller_application']
        else:
            if 'name' not in kwargs:
                raise ValueError("either 'controller_application' or 'name' must be provided")
            name = kwargs.get('name')
            da = kwargs.get('device_address', None)
            ca = ControllerApplication(name, da)

        self.j1939_dll.add_ca(ca)
        ca.associate_ecu(self)
        
        return ca

    def remove_ca(self, device_address):
        """Remove a ControllerApplication from the ECU.

        :param int device_address:
            A integer representing the device address

        :return:
            True if the ControllerApplication was successfully removed, otherwise False is returned.
        """
        return self.j1939_dll.remove_ca(device_address)

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit=0, frame_format=FrameFormat.FEFF):
        """send a pgn
        :param int data_page: data page
        :param int pdu_format: pdu format
        :param int pdu_specific: pdu specific
        :param int priority: message priority
        :param int src_address: address of the transmitter
        :param list data: payload, each list index represents one payload byte
        :param time_limit: option j1939-22 multi-pg: specify a time limit in s (e.g. 0.1 == 100ms),
        after this time, the multi-pg will be sent. several pgs can thus be combined in one multi-pg.
        0 or no time-limit means immediate sending.
        """
        return self.j1939_dll.send_pgn(data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit, frame_format)

    def send_message(self, can_id, extended_id, data, fd_format=False):
        """Send a raw CAN message to the bus.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads. (?)

        :param int can_id:
            CAN-ID of the message (always 29-bit)
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param fd_format:
            fd format means bitrate switching and payload of max 64Bytes is active

        :raises can.CanError:
            When the message fails to be transmitted
        """
        logger.debug("send_message | can_id {0} | extended_id {1}".format(can_id, extended_id))
        if not self._bus:
            raise RuntimeError("Not connected to CAN bus")
        self._bus.send(can_id, bytes(data), extended_id)
        # TODO: check error receivement

    def notify(self, can_id, data, timestamp):
        """Feed incoming CAN message into this ecu.

        If a custom interface is used, this function must be called for each
        29-bit standard message read from the CAN bus.

        :param int can_id:
            CAN-ID of the message (always 29-bit)
        :param bytearray data:
            Data part of the message (0 - 8 bytes)
        :param float timestamp:
            The timestamp field in a CAN message is a floating point number
            representing when the message was received since the epoch in
            seconds.
            Where possible this will be timestamped in hardware.
        """
        # ToDo
        #if msg.is_error_frame or msg.is_remote_frame or (msg.is_extended_id == False):
        #    return
        self.j1939_dll.notify(can_id, data, timestamp)

    def loop(self, now):
        
        self._bus.loop()

        next_wakeup = self.j1939_dll.loop(now)

        # check timer events
        for event in self._timer_events:
            if event['deadline'] > now:
                if next_wakeup > event['deadline']:
                    next_wakeup = event['deadline']
            else:
                # deadline reached
                logger.debug("Deadline for event reached")
                if event['callback']( event['cookie'] ) == True:
                    # "true" means the callback wants to be called again
                    while event['deadline'] < now:
                        # just to take care of overruns
                        event['deadline'] += event['delta_time']
                    # recalc next wakeup
                    if next_wakeup > event['deadline']:
                        next_wakeup = event['deadline']
                else:
                    # remove from list
                    self._timer_events.remove( event )

        time_to_sleep = next_wakeup - time.time()
        return time_to_sleep

    def _notify_subscribers(self, priority, pgn, sa, dest, timestamp, data):
        """Feed incoming message to subscribers.

        :param int priority:
            Priority of the message
        :param int pgn:
            Parameter Group Number of the message
        :param int sa:
            Source Address of the message
        :param int dest:
            Destination Address of the message
        :param int timestamp:
            Timestamp of the CAN message
        :param bytearray data:
            Data of the PDU
        """
        logger.debug("notify subscribers for PGN {}".format(pgn))
        # notify only the CA for which the message is intended
        # each CA receives all broadcast messages
        for dic in self._subscribers:
            if (dic['dev_adr'] == None) or (dest == ParameterGroupNumber.Address.GLOBAL) or (callable(dic['dev_adr']) and dic['dev_adr'](dest)) or (dest == dic['dev_adr']):
                dic['cb'](priority, pgn, sa, timestamp, data)

    def _is_message_acceptable(self, dest):
        for dic in self._subscribers:
            if dic['dev_adr'] == dest:
                return True
        return False
