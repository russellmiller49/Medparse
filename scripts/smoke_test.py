"""Deprecated wrapper. Use scripts/legacy/smoke_test.py"""
import runpy
if __name__ == "__main__":
    runpy.run_module("scripts.legacy.smoke_test", run_name="__main__")
