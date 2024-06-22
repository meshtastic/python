

class Event(object):
    """A simple event class."""

class Observable(object):
    """A class that represents an observable object.
    
    To publish an event call fire(type="progress", percent=50) or whatever.  It will call  
    """

    def __init__(self):
        """Initialize the Observable object."""
        self.callbacks = []

    def subscribe(self, callback):
        """Subscribe to the observable object.

        Args:
            callback (function): The callback function to be called when the event is fired.
        """
        self.callbacks.append(callback)

    def fire(self, **attrs):
        """Fire the event.

        Args:
            **attrs: Arbitrary keyword arguments to be passed to the callback functions.
        """
        e = Event()
        e.source = self
        for k, v in attrs.items():
            setattr(e, k, v)
        for fn in self.callbacks:
            fn(e)