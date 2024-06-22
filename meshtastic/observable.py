"""A basic implementation of the observer pattern."""

import typing

class Event:
    """A simple event class."""

    def __init__(self, source) -> None:
        self.source = source

    def __getattr__(self, name: str) -> typing.Any:
        """We dynamically add attributes to this class, so stub out __getattr__ so that mypy doesn't complain."""


class Observable:
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
        e = Event(self)
        for k, v in attrs.items():
            setattr(e, k, v)
        for fn in self.callbacks:
            fn(e)