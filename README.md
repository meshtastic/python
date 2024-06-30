# Meshtastic Python

[![codecov](https://codecov.io/gh/meshtastic/python/branch/master/graph/badge.svg?token=TIWPJL73KV)](https://codecov.io/gh/meshtastic/python)
![PyPI - Downloads](https://img.shields.io/pypi/dm/meshtastic)
[![CI](https://img.shields.io/github/actions/workflow/status/meshtastic/python/ci.yml?branch=master&label=actions&logo=github&color=yellow)](https://github.com/meshtastic/python/actions/workflows/ci.yml)
[![CLA assistant](https://cla-assistant.io/readme/badge/meshtastic/python)](https://cla-assistant.io/meshtastic/python)
[![Fiscal Contributors](https://opencollective.com/meshtastic/tiers/badge.svg?label=Fiscal%20Contributors&color=deeppink)](https://opencollective.com/meshtastic/)
![GPL-3.0](https://img.shields.io/badge/License-GPL%20v3-blue.svg)

## Overview

A Python client for use with Meshtastic devices.
This small library (and example application) provides an easy API for sending and receiving messages over mesh radios.
It also provides access to any of the operations/data available in the device user interface or the Android application.
Events are delivered using a publish-subscribe model, and you can subscribe to only the message types you are interested in.

**[Getting Started Guide](https://meshtastic.org/docs/software/python/cli/installation)**

(Documentation/API Reference is currently offline)

## Call for Contributors

This library and CLI has gone without a consistent maintainer for a while, and there's many improvements that could be made. We're all volunteers here and help is extremely appreciated, whether in implementing your own needs or helping maintain the library and CLI in general.

If you're interested in contributing but don't have specific things you'd like to work on, look at the roadmap below!

## Roadmap

This should always be considered a list in progress and flux -- inclusion doesn't guarantee implementation, and exclusion doesn't mean something's not wanted. GitHub issues are a great place to discuss ideas.

* Types
  * type annotations throughout the codebase, and upgrading mypy running in CI to `--strict`
* async-friendliness
* CLI completeness & consistency
  * the CLI should support all features of the firmware
  * there should be a consistent output format available for shell scripting
* CLI input validation & documentation
  * what arguments and options are compatible & incompatible with one another?
  * can the options be restructured in a way that is more self-documenting?
  * pubsub events should be documented clearly
* helpers for third-party code
  * it should be easy to write a script that supports similar options to the CLI so many tools support the same ways of connecting to nodes
* data storage & processing
  * there should be a standardized way of recording packets for later use, debugging, etc.
  * a persistence layer could also keep track of nodes beyond nodedb, as the apps do
  * a sqlite database schema and tools for writing to it may be a good starting point
  * enable maps, charts, visualizations

## Stats

![Alt](https://repobeats.axiom.co/api/embed/c71ee8fc4a79690402e5d2807a41eec5e96d9039.svg "Repobeats analytics image")
