"""
Globals singleton class.

The Global object is gone, as are all its setters and getters. Instead the
module itself is the singleton namespace, which can be imported into
whichever module is used. The associated tests have also been removed,
since we now rely on built in Python mechanisms.

This is intended to make the Python read more naturally, and to make the
intention of the code clearer and more compact. It is merely a sticking
plaster over the use of shared globals, but the coupling issues wil be dealt
with rather more easily once the code is simplified by this change.

"""

def reset():
    """
    """
    global args, parser, channel_index, logfile, tunnelInstance, camel_case
    args = None
    parser = None
    channel_index = None
    logfile = None
    tunnelInstance = None
    # TODO: to migrate to camel_case for v1.3 change this value to True
    camel_case = False

reset()