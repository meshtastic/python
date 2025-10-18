# Changelog

## [Issue #836] mDNS Discovery Enhancements (2025-10-18)

### Added
- Introduced a `--discover-mdns` CLI flag (with optional `--mdns-timeout`) to enumerate Meshtastic nodes advertising `_meshtastic._tcp` on the local network. (#836)
- Implemented TXT record decoding so discovery output highlights shortname, node ID, hardware model, firmware version, platform, and last-heard metadata. (#836)
- Added a mock advertiser script (`scripts/mock_mdns_server.py`) to broadcast configurable TXT fields for local testing. (#836)
- Created unit tests that cover dependency checks and discovery output formatting. (#836)

### Changed
- Adjusted version detection to report `development` when package metadata is unavailable, ensuring `python -m meshtastic` works from source trees. (#836)
- Suppressed duplicate TXT keys in the discovery output while still printing any remaining custom properties. (#836)

### Testing
- `python -m pytest meshtastic/tests/test_main.py::test_main_discover_mdns_outputs_services`
- `python scripts/mock_mdns_server.py --duration 0 --shortname LAB --id !123456 --firmware 2.4.1 --hardware RAK4631 --platform rp2040 --last-heard 2025-10-17T16:00:00Z`
- `python -m meshtastic --discover-mdns --mdns-timeout 2`

### Notes
- Dependencies installed during testing: `zeroconf`, `pytest`, `protobuf`, `pyserial`, `PyPubSub`, `tabulate`, `requests`, `bleak`.
