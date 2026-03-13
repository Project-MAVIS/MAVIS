# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

"""
Command-line entry point for launching the MAVIS Gradio UI.

Usage:
    python -m mavis.cmd.ui [OPTIONS]

Options:
    --host HOST       Host to bind to (default: 127.0.0.1)
    --port PORT       Port to bind to (default: 7860)
    --share           Create a public shareable link
    --debug           Enable debug mode
"""

import argparse
import sys


def main():
    """Main entry point for the UI launcher."""
    parser = argparse.ArgumentParser(
        description="Launch the MAVIS Steganography UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to bind to (default: 7860)",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public shareable link",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    args = parser.parse_args()

    # Import UI module (delayed to avoid import issues if dependencies are missing)
    try:
        from mavis.ui.ui import demo
    except ImportError as e:
        print(f"Error: Failed to port UI module: {e}", file=sys.stderr)
        print("Make sure all dependencies are installed.", file=sys.stderr)
        sys.exit(1)

    print(f"Starting MAVIS UI on http://{args.host}:{args.port}")
    if args.share:
        print("Creating public shareable link...")

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()

