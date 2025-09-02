"""Deprecated wrapper. Use scripts/legacy/validate_batch_results.py"""
import runpy
if __name__ == "__main__":
    runpy.run_module("scripts.legacy.validate_batch_results", run_name="__main__")
