import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

with open("README.md", "r") as fh:
    long_description = fh.read()

# This call to setup() does all the work
setup(
    name="meshtastic",
    version="0.7.8",
    description="Python API & client shell for talking to Meshtastic devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
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
    install_requires=["pyserial>=3.4", "protobuf>=3.6.1",
                      "pypubsub>=4.0.3", "dotmap>=1.3.14", "pexpect>=4.6.0",
                      "pygatt>=4.0.5"],
    python_requires='>=3.4',
    entry_points={
        "console_scripts": [
            "meshtastic=meshtastic.__main__:main"
        ]
    },
)
