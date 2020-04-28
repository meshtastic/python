import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# This call to setup() does all the work
setup(
    name="meshtastic",
    version="0.5.0",
    description="Python API & client shell for talking to Meshtastic devices",
    url="https://github.com/meshtastic/Meshtastic-python",
    author="Kevin Hester",
    author_email="kevinh@geeksville.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=["meshtastic"],
    include_package_data=True,
    install_requires=["pyserial>=3.4", "protobuf>=3.6.1", "pypubsub>=4.0.3"],
    python_requires='>=3',
    entry_points={
        "console_scripts": [
            "meshtastic=meshtastic.__main__:main",
        ]
    },
)
