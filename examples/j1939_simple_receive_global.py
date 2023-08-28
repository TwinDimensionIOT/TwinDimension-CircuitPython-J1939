import adafruit_logging as logging
import time
import j1939
import board

logging.getLogger('electronic_control_unit').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

def on_message(priority, pgn, sa, timestamp, data):
    """Receive incoming messages from the bus

    :param int priority:
        Priority of the message
    :param int pgn:
        Parameter Group Number of the message
    :param int sa:
        Source Address of the message
    :param int timestamp:
        Timestamp of the message
    :param bytearray data:
        Data of the PDU
    """
    print("PGN {} length {} data {}".format(pgn, len(data), data))

def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    ecu.connect(bus_type='mcp2515', bitrate=250000, cs = board.IO18, sck = board.IO6, mosi = board.IO7, miso = board.IO17)

    # subscribe to all (global) messages on the bus
    ecu.subscribe(on_message)

    startTime = time.time()
    now = time.time()
    while now - startTime < 120:
        # Explicitly pump the ecu loop.
        ecu.loop(now)
        now = time.time()

    print("Deinitializing")
    ecu.disconnect()

if __name__ == '__main__':
    main()