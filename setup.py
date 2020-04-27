import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="ezdevice",
    version="0.0.7",
    description="Python API & client shell for talking to Meshtastic devices",
    long_description=README,
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
    install_requires=["pyserial"],
    python_requires='>=3',
    entry_points={
        "console_scripts": [
            "meshtastic=meshtastic.__main__:main",
        ]
    },
)
