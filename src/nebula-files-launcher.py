#!/usr/bin/env python3
# Nebula Files Launcher - checks config and launches the right theme
# VERSION: v4.2.0

import json, os, subprocess, sys

CFG = os.path.expanduser("~/.config/nova-files/settings.json")

# Look for app files in multiple locations
SEARCH_PATHS = [
    os.path.dirname(os.path.abspath(__file__)),  # Same directory as launcher
    os.path.expanduser("~/.local/share/nebula-files"),
    os.path.expanduser("~/.local/share/nova-files"),
    "/opt/nova-files",
]

def get_theme():
    try:
        with open(CFG) as f:
            return json.load(f).get("theme", "nova")
    except:
        return "nova"

def find_app(name):
    for path in SEARCH_PATHS:
        full = os.path.join(path, name)
        if os.path.exists(full):
            return full
    return None

theme = get_theme()
if theme == "windows":
    app = find_app("nebula-files-win11.py")
else:
    app = find_app("nebula-files.py")

if not app:
    app = find_app("nebula-files.py")

if not app:
    print("Error: Could not find Nebula Files. Reinstall with install-nebula-files.sh")
    sys.exit(1)

os.execvp("python3", ["python3", app] + sys.argv[1:])
