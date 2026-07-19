#!/usr/bin/env python3
import sys

if "/usr/lib" not in sys.path:
    sys.path.insert(0, "/usr/lib")

from wifiportal.server import main

if __name__ == "__main__":
    main()
