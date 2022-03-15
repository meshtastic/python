import sys
import meshtastic
import meshtastic.tcp_interface

node_ip = "192.168.42.1"
iface = meshtastic.tcp_interface.TCPInterface(node_ip)
my_node_num = iface.myInfo.my_node_num
pos = iface.nodesByNum[my_node_num]["position"]
print (pos)

iface.close()

