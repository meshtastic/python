"""Globals singleton class.

   Instead of using a global, stuff your variables in this "trash can".
   This is not much better than using python's globals, but it allows
   us to better test meshtastic. Plus, there are some weird python
   global issues/gotcha that we can hopefully avoid by using this
   class instead.

"""

class Globals:
    """Globals class is a Singleton."""
    __instance = None

    @staticmethod
    def getInstance():
        """Get an instance of the Globals class."""
        if Globals.__instance is None:
            Globals()
        return Globals.__instance

    def __init__(self):
        """Constructor for the Globals CLass"""
        if Globals.__instance is not None:
            raise Exception("This class is a singleton")
        else:
            Globals.__instance = self
        self.args = None
        self.parser = None
        self.target_node = None
        self.channel_index = None
        self.logfile = None
        self.tunnelInstance = None

    def reset(self):
        """Reset all of our globals. If you add a member, add it to this method, too."""
        self.args = None
        self.parser = None
        self.target_node = None
        self.channel_index = None
        self.logfile = None
        self.tunnelInstance = None

    # setters
    def set_args(self, args):
        """Set the args"""
        self.args = args

    def set_parser(self, parser):
        """Set the parser"""
        self.parser = parser

    def set_target_node(self, target_node):
        """Set the target_node"""
        self.target_node = target_node

    def set_channel_index(self, channel_index):
        """Set the channel_index"""
        self.channel_index = channel_index

    def set_logfile(self, logfile):
        """Set the logfile"""
        self.logfile = logfile

    def set_tunnelInstance(self, tunnelInstance):
        """Set the tunnelInstance"""
        self.tunnelInstance = tunnelInstance

    # getters
    def get_args(self):
        """Get args"""
        return self.args

    def get_parser(self):
        """Get parser"""
        return self.parser

    def get_target_node(self):
        """Get target_node"""
        return self.target_node

    def get_channel_index(self):
        """Get channel_index"""
        return self.channel_index

    def get_logfile(self):
        """Get logfile"""
        return self.logfile

    def get_tunnelInstance(self):
        """Get tunnelInstance"""
        return self.tunnelInstance
