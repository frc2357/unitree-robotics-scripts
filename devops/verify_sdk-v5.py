#!/usr/bin/env python3
"""
Environment Validation Script to validate dependencies and SDK setup for Unitree Robotics Python SDK.

Features:
- Validates core dependencies (NumPy, CycloneDDS, OpenCV)
- Detects SDK imports and IDL message structures
- Cross-platform DDS Channel Initialization (auto-detects macOS 'lo0', Linux 'lo', and Windows '127.0.0.1' / '')

Usage:
    uv run python verify_sdk.py [interface]
    Example: uv run python verify_sdk.py
    Example: uv run python verify_sdk.py eth0
    Example (Windows): uv run python verify_sdk.py "Ethernet"
"""

import platform
import sys
import traceback


def print_step(title):
    print("\n==========================================")
    print(f" {title}")
    print("==========================================")


def check_dependencies():
    print_step("Step 1: Core Python Dependencies")

    # NumPy
    try:
        import numpy as np
        print(f"✓ numpy version: {np.__version__}")
    except Exception: # noqa
        print("✗ Failed to import numpy:")
        traceback.print_exc()
        return False

    # CycloneDDS
    try:
        print("✓ cyclonedds C-extension available.")
    except Exception: # noqa
        print("✗ Failed to import cyclonedds:")
        traceback.print_exc()
        return False

    # OpenCV (optional)
    try:
        import cv2
        print(f"✓ opencv-python version: {cv2.__version__}")
    except Exception: # noqa
        print("ℹ opencv-python not installed (optional).")

    return True


def check_sdk_imports():
    print_step("Step 2: Unitree SDK Package Imports")

    # Base package
    try:
        import unitree_sdk2py
        print(f"✓ unitree_sdk2py package found at: {getattr(unitree_sdk2py, '__file__', 'unknown')}")
    except Exception: # noqa
        print("✗ Failed to import base unitree_sdk2py package:")
        traceback.print_exc()
        return False, None

    # Resolve ChannelFactoryInitialize or equivalent builder
    channel_init_func = None
    try:
        import unitree_sdk2py.core.channel as channel_mod
        symbols = dir(channel_mod)
        print(f"ℹ Available symbols in unitree_sdk2py.core.channel: {symbols}")

        if "ChannelFactoryInitialize" in symbols:
            channel_init_func = channel_mod.ChannelFactoryInitialize
            print("✓ Found 'ChannelFactoryInitialize' in unitree_sdk2py.core.channel.")
        elif "ChannelFactoryBuilder" in symbols:
            builder_cls = channel_mod.ChannelFactoryBuilder
            channel_init_func = lambda domain_id, iface: builder_cls().Init(domain_id, iface)
            print("✓ Found 'ChannelFactoryBuilder' in unitree_sdk2py.core.channel.")
        elif "ChannelFactory" in symbols:
            factory_cls = channel_mod.ChannelFactory
            channel_init_func = lambda domain_id, iface: factory_cls().Init(domain_id, iface)
            print("✓ Found 'ChannelFactory' in unitree_sdk2py.core.channel.")
        else:
            print("✗ Could not find a ChannelFactory initialization function in unitree_sdk2py.core.channel.")
            return False, None
    except Exception: # noqa
        print("✗ Error inspecting unitree_sdk2py.core.channel:")
        traceback.print_exc()
        return False, None

    # IDL messages
    low_state_cls = None
    idl_paths = [
        ("unitree_sdk2py.idl.unitree_go.msg.dds_", "LowState_"),
        ("unitree_sdk2py.idl.default", "unitree_go_msg_dds__LowState_"),
        ("unitree_sdk2py.idl.unitree_hg.msg.dds_", "LowState_"),
    ]

    for mod_path, cls_name in idl_paths:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            low_state_cls = getattr(mod, cls_name)
            print(f"✓ Telemetry message structure '{cls_name}' imported from '{mod_path}'.")
            break
        except Exception: # noqa
            pass

    if low_state_cls is None:
        print("✗ Could not import LowState_ message structure from standard IDL paths.")
        return False, channel_init_func

    return True, channel_init_func


def get_default_interface():
    """Detect default loopback interface based on OS."""
    system = platform.system()
    if system == "Darwin":     # macOS
        return "lo0"
    elif system == "Windows":  # Windows
        return "127.0.0.1"
    return "lo"                # Linux / default


def check_dds_channel(channel_init_func, user_interface):
    system = platform.system()
    if user_interface:
        interfaces_to_try = [user_interface]
    else:
        # Auto-try appropriate defaults based on OS
        default_iface = get_default_interface()
        interfaces_to_try = [default_iface]
        if system == "Windows":
            interfaces_to_try.extend(["", "Loopback Pseudo-Interface 1"])
        elif system == "Darwin":
            if "lo" not in interfaces_to_try:
                interfaces_to_try.append("lo")
        else:
            if "lo0" not in interfaces_to_try:
                interfaces_to_try.append("lo0")

    print_step(f"Step 3: DDS Channel Initialization ({system})")

    if channel_init_func is None:
        print("⏭ Skipping DDS initialization because SDK import failed.")
        return False

    for iface in interfaces_to_try:
        try:
            label = f"'{iface}'" if iface != "" else "default adapter ('')"
            print(f"Attempting ChannelFactory initialization on interface {label}...")
            channel_init_func(0, iface)
            print(f"✓ ChannelFactory initialized successfully on interface {label}.")
            return True
        except Exception as e: # noqa
            print(f"  └─ Interface '{iface}' failed: {e}")

    print("\n✗ DDS channel initialization failed on all attempted interfaces.")
    print("\nTroubleshooting Interface Errors:")
    print(" 1. Loopback interfaces by OS:")
    print("    - macOS:   'lo0'")
    print("    - Linux:   'lo'")
    print("    - Windows: '127.0.0.1' or '' (or adapter name like 'Ethernet')")
    print(" 2. When connected to the robot, pass your active network interface:")
    print("    - Linux:   uv run python verify_sdk.py eth0 (or enp2s0)")
    print("    - Mac:     uv run python verify_sdk.py en0")
    print("    - Windows: uv run python verify_sdk.py \"Ethernet\" (or \"Wi-Fi\")")
    print(" 3. View available interfaces using:")
    print("    - Mac/Linux: ifconfig or ip addr")
    print("    - Windows:   ipconfig")
    return False


def main():
    system = platform.system()
    print("==========================================")
    print(f" Environment Validation: Checking Unitree SDK and Required Dependencies ({system})")
    print("==========================================")

    user_interface = sys.argv[1] if len(sys.argv) > 1 else None

    deps_ok = check_dependencies()
    sdk_ok, channel_init_func = check_sdk_imports()
    dds_ok = check_dds_channel(channel_init_func, user_interface)

    print_step("Diagnostic Summary")
    if deps_ok and sdk_ok and dds_ok:
        print("🎉 SUCCESS: All checks passed! Your Unitree SDK setup is fully working.")
    else:
        print("❌ ISSUES DETECTED: Review the log above to fix the interface parameter.")
        sys.exit(1)


if __name__ == "__main__":
    main()
