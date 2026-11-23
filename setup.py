#!/usr/bin/env python3
"""
GIGASEEK OSINT Framework
Creator: Anonymous-beta
Demon-themed professional OSINT toolkit
"""

from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="gigaseek",
    version="1.0.0",
    author="Anonymous-beta",
    author_email="",
    description="Demon-themed OSINT framework with super crawler capabilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Anonymous-beta/GIGASEEK",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Information Technology",
        "Topic :: Security",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gigaseek=gigaseek.__main__:main",
        ],
    },
    include_package_data=True,
    package_data={
        "gigaseek": ["data/*.json", "data/*.txt"],
    },
)
