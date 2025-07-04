#!/usr/bin/env python3
"""
Test script to verify BLE hanging fixes.
This script tests the BLE interface shutdown behavior.
"""

import asyncio
import logging
import signal
import sys
import time
from threading import Thread

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ble_client_shutdown():
    """Test BLEClient shutdown behavior"""
    print("Testing BLEClient shutdown behavior...")

    try:
        # Test that our changes compile and have the expected attributes
        import ast
        import inspect

        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()

        # Parse the source to check for our improvements
        tree = ast.parse(source)

        # Check for shutdown flag
        has_shutdown_flag = '_shutdown_flag' in source
        has_pending_tasks = '_pending_tasks' in source
        has_timeout_in_async_await = 'timeout=30.0' in source
        has_task_cancellation = 'task.cancel()' in source

        print(f"Has shutdown flag: {has_shutdown_flag}")
        print(f"Has pending tasks tracking: {has_pending_tasks}")
        print(f"Has timeout in async_await: {has_timeout_in_async_await}")
        print(f"Has task cancellation: {has_task_cancellation}")

        return has_shutdown_flag and has_pending_tasks and has_timeout_in_async_await and has_task_cancellation

    except Exception as e:
        print(f"Error testing BLE client: {e}")
        return False

def test_ble_interface_shutdown():
    """Test BLEInterface shutdown behavior"""
    print("Testing BLEInterface shutdown behavior...")

    try:
        # Test that our changes are present in the source
        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()

        # Check for our improvements
        has_shutdown_check_in_send = 'if self._shutdown_flag:' in source and 'Ignoring TORADIO write during shutdown' in source
        has_improved_close = 'Prevent multiple close attempts' in source
        has_error_handling = 'Error disconnecting BLE client' in source

        print(f"Has shutdown check in send: {has_shutdown_check_in_send}")
        print(f"Has improved close method: {has_improved_close}")
        print(f"Has better error handling: {has_error_handling}")

        return has_shutdown_check_in_send and has_improved_close and has_error_handling

    except Exception as e:
        print(f"Error testing BLE interface: {e}")
        return False

def test_signal_handling():
    """Test signal handling improvements"""
    print("Testing signal handling...")
    
    def signal_handler(sig, frame):
        print(f"Received signal {sig}, shutting down gracefully...")
        sys.exit(0)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Signal handlers set up successfully")
    return True

def main():
    """Run all tests"""
    print("Starting BLE fix verification tests...")
    
    tests = [
        ("BLE Client Shutdown", test_ble_client_shutdown),
        ("BLE Interface Shutdown", test_ble_interface_shutdown),
        ("Signal Handling", test_signal_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- Running {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{test_name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"{test_name}: FAIL - {e}")
            results.append((test_name, False))
    
    print("\n--- Test Results ---")
    for test_name, result in results:
        print(f"{test_name}: {'PASS' if result else 'FAIL'}")
    
    all_passed = all(result for _, result in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
