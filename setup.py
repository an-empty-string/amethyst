#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="amethyst_extensions",
    version="0.0.1",
    description="Extensions for the Amethyst server",
    author="Tris Emmy Wilson",
    author_email="tris@tris.fyi",
    packages=find_packages(),
    entry_points={
        "amethyst.resources": [
            "pydoc = amethyst_ext.pydoc:PydocResource",
            "redirect = amethyst_ext.redirect:RedirectResource",
        ],
    },
)

