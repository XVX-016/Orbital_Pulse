#!/usr/bin/env python3
"""
Automated setup script to apply the MPT import patch to GeoChat repository.
Run this script after cloning GeoChat into ml/geochat/GeoChat.
"""

import os
import sys

TARGET_FILE = os.path.join("ml", "geochat", "GeoChat", "geochat", "model", "__init__.py")

def apply_patch():
    if not os.path.exists(TARGET_FILE):
        print(f"[ERROR] Target file not found: {TARGET_FILE}")
        print("Please clone GeoChat repository first: git clone https://github.com/mbzuai-oryx/GeoChat.git ml/geochat/GeoChat")
        sys.exit(1)

    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    target_str = "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"
    replacement_str = (
        "try:\n"
        "    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig\n"
        "except ImportError:\n"
        "    pass"
    )

    if "except ImportError:" in content:
        print("[INFO] MPT import patch is already applied.")
        return

    if target_str in content:
        new_content = content.replace(target_str, replacement_str)
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[SUCCESS] Applied MPT import patch to geochat/model/__init__.py")
    else:
        print("[WARN] Target import line not found in file. Skipping patch.")

if __name__ == "__main__":
    apply_patch()
