#!/usr/bin/env python3
"""My CLI Tool — edit this to build your tool."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="My CLI Tool")
    parser.add_argument("--name", default="World", help="Name to greet")
    args = parser.parse_args()
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
