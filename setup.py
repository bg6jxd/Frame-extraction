#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="videoframe",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "videoframe=videoframe.cli.main:cli",
        ],
    },
    python_requires=">=3.10",
)
