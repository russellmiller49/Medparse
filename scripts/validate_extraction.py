#!/usr/bin/env python3
"""Deprecated wrapper. Use scripts/legacy/validate_extraction.py"""
import runpy

if __name__ == "__main__":
    runpy.run_module("scripts.legacy.validate_extraction", run_name="__main__")

