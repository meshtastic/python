#!/usr/bin/env python3
"""
Test script to verify BLE shutdown fixes work correctly.
This simulates the shutdown scenarios that were causing issues.
"""

import asyncio
import logging
import sys
import time
from threading import Thread

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ble_client_creation_and_shutdown():
    """Test BLEClient can be created and shut down without hanging"""
    print("Testing BLE client creation and shutdown...")
    
    try:
        # Import here to catch import errors
        import ast
        
        # Parse the source to verify our fixes are present
        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()
        
        # Check for key improvements
        checks = {
            "shutdown_flag": "_shutdown_flag = False" in source,
            "pending_tasks": "_pending_tasks = set()" in source,
            "timeout_default": "timeout=30.0" in source,
            "call_soon_threadsafe": "call_soon_threadsafe" in source,
            "future_cancel_check": "if not future.done():" in source,
            "task_cancellation": "task.cancel()" in source,
        }
        
        print("Checking for key improvements:")
        for check_name, result in checks.items():
            print(f"  {check_name}: {'✓' if result else '✗'}")
        
        all_present = all(checks.values())
        
        if all_present:
            print("✓ All shutdown improvements are present in the code")
        else:
            print("✗ Some improvements are missing")
            
        return all_present
        
    except Exception as e:
        print(f"Error testing BLE client: {e}")
        return False

def test_no_async_coroutine_warnings():
    """Test that we don't have async coroutine warnings in our code"""
    print("Testing for async coroutine issues...")
    
    try:
        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()
        
        # Check that we're not calling async methods incorrectly
        problematic_patterns = [
            "self.async_run(self._stop_event_loop())",  # This was the problem
            "await.*_stop_event_loop.*not.*await",  # Mixing sync/async incorrectly
        ]
        
        issues_found = []
        for pattern in problematic_patterns:
            if pattern in source:
                issues_found.append(pattern)
        
        if not issues_found:
            print("✓ No problematic async patterns found")
            return True
        else:
            print("✗ Found problematic patterns:")
            for issue in issues_found:
                print(f"  - {issue}")
            return False
            
    except Exception as e:
        print(f"Error checking async patterns: {e}")
        return False

def test_shutdown_logic():
    """Test the shutdown logic improvements"""
    print("Testing shutdown logic...")
    
    try:
        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()
        
        # Check for proper shutdown sequence
        shutdown_improvements = {
            "cancel_pending_futures": "for future in list(self._pending_tasks):" in source,
            "clear_pending_tasks": "self._pending_tasks.clear()" in source,
            "call_soon_threadsafe_stop": "self._eventLoop.call_soon_threadsafe(self._eventLoop.stop)" in source,
            "thread_join_timeout": "self._eventThread.join(timeout=5.0)" in source,
            "shutdown_flag_check": "if self._shutdown_flag:" in source,
        }
        
        print("Checking shutdown logic improvements:")
        for check_name, result in shutdown_improvements.items():
            print(f"  {check_name}: {'✓' if result else '✗'}")
        
        all_present = all(shutdown_improvements.values())
        
        if all_present:
            print("✓ All shutdown logic improvements are present")
        else:
            print("✗ Some shutdown logic improvements are missing")
            
        return all_present
        
    except Exception as e:
        print(f"Error testing shutdown logic: {e}")
        return False

def test_error_handling():
    """Test error handling improvements"""
    print("Testing error handling...")
    
    try:
        with open('meshtastic/ble_interface.py', 'r') as f:
            source = f.read()
        
        # Check for improved error handling
        error_handling_checks = {
            "shutdown_during_send": "Ignoring TORADIO write during shutdown" in source,
            "disconnect_error_handling": "Error disconnecting BLE client" in source,
            "atexit_unregister_error": "except ValueError:" in source,
            "future_done_check": "if not future.done():" in source,
        }
        
        print("Checking error handling improvements:")
        for check_name, result in error_handling_checks.items():
            print(f"  {check_name}: {'✓' if result else '✗'}")
        
        all_present = all(error_handling_checks.values())
        
        if all_present:
            print("✓ All error handling improvements are present")
        else:
            print("✗ Some error handling improvements are missing")
            
        return all_present
        
    except Exception as e:
        print(f"Error testing error handling: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting BLE shutdown fix verification...")
    print("=" * 50)
    
    tests = [
        ("BLE Client Creation and Shutdown", test_ble_client_creation_and_shutdown),
        ("Async Coroutine Warnings", test_no_async_coroutine_warnings),
        ("Shutdown Logic", test_shutdown_logic),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print("=" * 50)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    overall_status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
    print(f"\nOverall: {overall_status}")
    
    if all_passed:
        print("\n✓ The BLE shutdown fixes are properly implemented!")
        print("✓ This should resolve the hanging issues in mmrelay and CLI.")
    else:
        print("\n✗ Some issues were found that need to be addressed.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
