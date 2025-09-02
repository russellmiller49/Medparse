"""Deprecated wrapper. Use scripts/legacy/smoke_check_output.py"""
import runpy
if __name__ == "__main__":
    runpy.run_module("scripts.legacy.smoke_check_output", run_name="__main__")
