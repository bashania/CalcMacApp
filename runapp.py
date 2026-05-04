#!/usr/bin/env python3
"""Entry-point voor py2app — voert app.main.main() uit.

py2app heeft een top-level script nodig om de bundel om heen te bouwen.
Vanuit de Terminal blijft `python3 -m app.main` het normale startpad.
"""

from app.main import main

if __name__ == '__main__':
    main()
