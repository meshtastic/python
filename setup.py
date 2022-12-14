# Note: you shouldn't need to run this script manually.  It is run implicitly by the pip3 install command.

import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

with open("README.md", "r") as fh:
    long_description = fh.read()

# This call to setup() does all the work
setup(
    name="BlackLager",
    version="1.0.2",
    description="Python API & client shell for sending encrypted messages to Meshtastic devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/black-lager/python",
    author="Black Lager Developers",
    author_email="mkrizek@dons.usfca.edu, akadd8@gmail.com",
    license="GPL-3.0-only",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    packages=["meshtastic"],
    include_package_data=True,
    install_requires=["pyserial>=3.4", "protobuf>=3.13.0",
                      "pypubsub>=4.0.3", "dotmap>=1.3.14", "pexpect>=4.6.0", "pyqrcode>=1.2.1",
                      "tabulate>=0.8.9", "timeago>=1.0.15", "pyyaml", "geopy>=2.3.0",
                      "pygatt>=4.0.5 ; platform_system=='Linux'"],
    extras_require={
        'tunnel': ["pytap2>=2.0.0"]
    },
    python_requires='>=3.7',
    entry_points={
        "console_scripts": [
            "blacklager=black_lager_app.__main__:main",
            "meshtastic=meshtastic.__main__:main",
            "mesh-tunnel=meshtastic.__main__:tunnelMain [tunnel]"
        ]
    },
)
