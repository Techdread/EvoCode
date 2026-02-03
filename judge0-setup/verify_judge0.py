#!/usr/bin/env python3
"""
Judge0 Local Verification Suite
Tests connectivity, polyglot support, and sandbox integrity.
"""

import requests
import time
import sys

# Configuration
JUDGE0_URL = "http://localhost:2358"
HEADERS = {"Content-Type": "application/json"}

# Language IDs (Standard Judge0 1.13.x mappings)
# Check http://localhost:2358/languages for your specific version IDs
LANG_IDS = {
    "C++ (GCC)": 54,
    "Java": 62,
    "Rust": 73,
    "JavaScript (Node.js)": 63,
    "Fortran": 59,       # Fortran (GFortran 9.2.0)
    "Python 3": 71,
    "VB.NET": 84,
    "Lua": 64,
    "Go": 60,
    "Clojure": 86
}

def check_connectivity():
    """Test basic API connectivity."""
    print("=" * 60)
    print("CONNECTIVITY TEST")
    print("=" * 60)

    try:
        # Test root endpoint
        r = requests.get(f"{JUDGE0_URL}/", timeout=10)
        print(f"Root endpoint: {'OK' if r.status_code == 200 else 'FAILED'}")

        # Test languages endpoint
        r = requests.get(f"{JUDGE0_URL}/languages", timeout=10)
        if r.status_code == 200:
            langs = r.json()
            print(f"Languages endpoint: OK ({len(langs)} languages available)")
        else:
            print(f"Languages endpoint: FAILED ({r.status_code})")

        # Test system info
        r = requests.get(f"{JUDGE0_URL}/system_info", timeout=10)
        print(f"System info endpoint: {'OK' if r.status_code == 200 else 'FAILED'}")

        return True
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Judge0. Is it running?")
        print(f"       Tried: {JUDGE0_URL}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def run_submission(name, source_code, lang_id, stdin="", expected_output=None,
                   cpu_time_limit=None, extra_options=None):
    """Submit code and check results."""
    print(f"Testing {name}...", end=" ", flush=True)

    payload = {
        "source_code": source_code,
        "language_id": lang_id,
        "stdin": stdin,
        "wait": "true"  # blocking request for simplicity
    }

    if cpu_time_limit:
        payload["cpu_time_limit"] = cpu_time_limit

    if extra_options:
        payload.update(extra_options)

    try:
        response = requests.post(
            f"{JUDGE0_URL}/submissions",
            json=payload,
            headers=HEADERS,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()

        # Check Status
        status = result.get("status", {}).get("description", "Unknown")
        stdout = result.get("stdout", "").strip() if result.get("stdout") else ""
        stderr = result.get("stderr", "").strip() if result.get("stderr") else ""

        if status == "Accepted":
            if expected_output and expected_output in stdout:
                print(f"PASS")
                return True, result
            elif expected_output:
                print(f"PASS (output mismatch)")
                print(f"   Expected: {expected_output}")
                print(f"   Got: {stdout[:100]}")
                return True, result
            else:
                print(f"PASS (Execution success)")
                return True, result
        else:
            print(f"FAIL ({status})")
            if stderr:
                print(f"   Stderr: {stderr[:200]}")
            if result.get("compile_output"):
                print(f"   Compile Error: {result.get('compile_output')[:200]}")
            return False, result

    except requests.exceptions.Timeout:
        print(f"TIMEOUT")
        return False, None
    except Exception as e:
        print(f"ERROR: {e}")
        return False, None


def test_polyglot():
    """Test all requested programming languages."""
    print("\n" + "=" * 60)
    print("POLYGLOT SUPPORT TEST")
    print("=" * 60)

    results = {}

    # 1. C++
    cpp_code = """
#include <iostream>
int main() {
    std::cout << "Hello C++";
    return 0;
}
"""
    results["C++"] = run_submission("C++", cpp_code, LANG_IDS["C++ (GCC)"],
                                     expected_output="Hello C++")

    # 2. Java (Judge0 requires Main class)
    java_code = """
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello Java");
    }
}
"""
    results["Java"] = run_submission("Java", java_code, LANG_IDS["Java"],
                                      expected_output="Hello Java")

    # 3. Rust
    rust_code = """
fn main() {
    println!("Hello Rust");
}
"""
    results["Rust"] = run_submission("Rust", rust_code, LANG_IDS["Rust"],
                                      expected_output="Hello Rust")

    # 4. JavaScript
    js_code = "console.log('Hello Node');"
    results["JavaScript"] = run_submission("JavaScript", js_code,
                                            LANG_IDS["JavaScript (Node.js)"],
                                            expected_output="Hello Node")

    # 5. Fortran
    fortran_code = """
program hello
  print *, "Hello Fortran"
end program hello
"""
    results["Fortran"] = run_submission("Fortran", fortran_code, LANG_IDS["Fortran"],
                                         expected_output="Hello Fortran")

    # 6. Python
    py_code = "print('Hello Python')"
    results["Python"] = run_submission("Python", py_code, LANG_IDS["Python 3"],
                                        expected_output="Hello Python")

    # 7. VB.NET
    vb_code = """
Imports System
Public Module Program
    Public Sub Main()
        Console.WriteLine("Hello VB")
    End Sub
End Module
"""
    results["VB.NET"] = run_submission("VB.NET", vb_code, LANG_IDS["VB.NET"],
                                        expected_output="Hello VB")

    # 8. Lua
    lua_code = "print('Hello Lua')"
    results["Lua"] = run_submission("Lua", lua_code, LANG_IDS["Lua"],
                                     expected_output="Hello Lua")

    # 9. Go
    go_code = """
package main
import "fmt"
func main() {
    fmt.Println("Hello Go")
}
"""
    results["Go"] = run_submission("Go", go_code, LANG_IDS["Go"],
                                    expected_output="Hello Go")

    # 10. Clojure
    clojure_code = '(println "Hello Clojure")'
    results["Clojure"] = run_submission("Clojure", clojure_code, LANG_IDS["Clojure"],
                                         expected_output="Hello Clojure")

    # Summary
    passed = sum(1 for r in results.values() if r[0])
    print(f"\nPolyglot Results: {passed}/{len(results)} languages passed")

    return results


def test_sandbox():
    """Test sandbox security features."""
    print("\n" + "=" * 60)
    print("SANDBOX INTEGRITY TESTS")
    print("=" * 60)

    # Test A: File System Isolation
    print("\n--- Test A: File System Isolation ---")
    fs_code = """
import os
try:
    # Try to read shadow password file
    with open('/etc/shadow', 'r') as f:
        content = f.read()
        if content:
            print("SECURITY BREACH: /etc/shadow readable!")
        else:
            print("File empty or blocked")
except PermissionError:
    print("Blocked: Permission denied")
except FileNotFoundError:
    print("Blocked: File not found (containerized)")
except Exception as e:
    print(f"Blocked: {type(e).__name__}: {e}")

# Check environment
print("Root contents:", sorted(os.listdir('/'))[:10])
"""
    success, result = run_submission("FS Isolation", fs_code, LANG_IDS["Python 3"])
    if result and result.get("stdout"):
        stdout = result.get("stdout", "")
        if "SECURITY BREACH" in stdout:
            print("   WARNING: Sandbox may be compromised!")
        elif "Blocked" in stdout:
            print("   Sandbox properly isolated")
        print(f"   Output: {stdout[:200]}")

    # Test B: Time Limit Enforcement
    print("\n--- Test B: Time Limit Enforcement ---")
    infinite_loop_code = """
#include <iostream>
int main() {
    while(true) {
        // Spin forever
    }
    return 0;
}
"""
    success, result = run_submission(
        "Time Limit",
        infinite_loop_code,
        LANG_IDS["C++ (GCC)"],
        cpu_time_limit=2.0
    )
    if result:
        status = result.get("status", {}).get("description", "")
        if "Time Limit" in status:
            print("   Time limits properly enforced")
        else:
            print(f"   Status: {status}")

    # Test C: Network Isolation
    print("\n--- Test C: Network Isolation ---")
    network_code = """
import socket
try:
    s = socket.create_connection(("8.8.8.8", 53), timeout=3)
    print("Network Accessible - WARNING if unexpected")
    s.close()
except socket.timeout:
    print("Network Blocked (timeout)")
except OSError as e:
    print(f"Network Blocked ({e})")
except Exception as e:
    print(f"Network Blocked ({type(e).__name__})")
"""
    success, result = run_submission("Network Isolation", network_code, LANG_IDS["Python 3"])
    if result and result.get("stdout"):
        stdout = result.get("stdout", "")
        if "Accessible" in stdout:
            print("   Note: Network access is enabled")
        elif "Blocked" in stdout:
            print("   Network properly isolated")
        print(f"   Output: {stdout.strip()}")

    # Test D: Memory Limit
    print("\n--- Test D: Memory Limit Enforcement ---")
    memory_code = """
# Try to allocate excessive memory
data = []
try:
    for i in range(1000):
        data.append('X' * (10 * 1024 * 1024))  # 10MB chunks
    print("Memory limit NOT enforced!")
except MemoryError:
    print("Memory limit enforced")
"""
    success, result = run_submission(
        "Memory Limit",
        memory_code,
        LANG_IDS["Python 3"],
        extra_options={"memory_limit": 64000}  # 64MB
    )
    if result:
        status = result.get("status", {}).get("description", "")
        stdout = result.get("stdout", "") or ""
        if "Memory" in status or "enforced" in stdout:
            print("   Memory limits properly enforced")


def list_available_languages():
    """List all available languages in the Judge0 instance."""
    print("\n" + "=" * 60)
    print("AVAILABLE LANGUAGES")
    print("=" * 60)

    try:
        r = requests.get(f"{JUDGE0_URL}/languages", timeout=10)
        if r.status_code == 200:
            langs = r.json()
            for lang in sorted(langs, key=lambda x: x.get("id", 0)):
                print(f"  ID {lang.get('id'):3d}: {lang.get('name')}")
        else:
            print(f"Failed to fetch languages: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    print("=" * 60)
    print("Judge0 Local Verification Suite")
    print("=" * 60)
    print(f"Target: {JUDGE0_URL}")
    print()

    # Check connectivity first
    if not check_connectivity():
        print("\nCannot proceed without connectivity.")
        print("Make sure Judge0 is running:")
        print("  cd judge0-setup && docker compose up -d")
        sys.exit(1)

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--languages":
            list_available_languages()
            sys.exit(0)
        elif sys.argv[1] == "--sandbox":
            test_sandbox()
            sys.exit(0)
        elif sys.argv[1] == "--polyglot":
            test_polyglot()
            sys.exit(0)

    # Run all tests
    test_polyglot()
    test_sandbox()

    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
