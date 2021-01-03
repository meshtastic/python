import sys
import meshtastic
import datetime, logging
from pubsub import pub

#logging.basicConfig(level=logging.DEBUG)
print(str(datetime.datetime.now()) + ": start")
interface = meshtastic.TCPInterface(sys.argv[1])
print(str(datetime.datetime.now()) + ": middle")
interface.close()
print(str(datetime.datetime.now()) + ": after close")