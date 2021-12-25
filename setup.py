#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="amethyst",
    version="0.0.1",
    description="A Gemini server",
    author="Tris Emmy Wilson",
    author_email="tris@tris.fyi",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "amethyst = amethyst.kindergarten:cli",
        ],
        "amethyst.resources": [
            "filesystem = amethyst.resource:FilesystemResource",
        ]
    },
    install_requires=[
        "cryptography",
    ]
)
