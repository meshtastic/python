# Contributing to Meshtastic Python

## Development resources
- [API Documentation](https://python.meshtastic.org/)
- [Meshtastic Python Development](https://meshtastic.org/docs/development/python/)
- [Building Meshtastic Python](https://meshtastic.org/docs/development/python/building/)
- [Using the Meshtastic Python Library](https://meshtastic.org/docs/development/python/library/)

## How to check your code (pytest/pylint) before a PR
- [Pre-requisites](https://meshtastic.org/docs/development/python/building/#pre-requisites)
- also execute `poetry install --all-extras --with dev,powermon` for all optional dependencies
- check your code with github ci actions locally
    - You need to have act installed. You can get it at https://nektosact.com/ 
    - on linux: `act -P ubuntu-latest=-self-hosted --matrix "python-version:3.12"`
    - on windows:
      - linux checks (linux docker): `act --matrix "python-version:3.12"`
      - windows checks (windows host): `act -P ubuntu-latest=-self-hosted --matrix "python-version:3.12"`
- or run all locally:
    - run `poetry run pylint meshtastic examples/ --ignore-patterns ".*_pb2.pyi?$"`
    - run `poetry run mypy meshtastic/`
    - run `poetry run pytest`
    - more commands see [CI workflow](https://github.com/meshtastic/python/blob/master/.github/workflows/ci.yml)
