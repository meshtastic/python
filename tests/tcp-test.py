
# reported by @ScriptBlock

import meshtastic, sys
from pubsub import pub
def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    print(interface.myInfo)
    interface.close()
pub.subscribe(onConnection, "meshtastic.connection.established")
interface = meshtastic.TCPInterface(sys.argv[1])
