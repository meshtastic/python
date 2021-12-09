"""Globals singleton class.

   Instead of using a global, stuff your variables in this "trash can".
   This is not much better than using python's globals, but it allows
   us to better test meshtastic. Plus, there are some weird python
   global issues/gotcha that we can hopefully avoid by using this
   class in stead.
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

    def set_args(self, args):
        """Set the args"""
        self.args = args

    def set_parser(self, parser):
        """Set the parser"""
        self.parser = parser

    def get_args(self):
        """Get args"""
        return self.args

    def get_parser(self):
        """Get parser"""
        return self.parser
