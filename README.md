# Amethyst

This repository contains the source code for two projects.

## amethyst

Amethyst is a server for the [Gemini](https://gemini.circumlunar.space)
protocol, written in Python. It's designed for extensibility (using the
setuptools/importlib `entry_points` API) and ease of use.

You can learn more about Amethyst in Geminispace at
( gemini://tris.fyi/projects/amethyst/ ).

## amethyst_extensions

This tree contains extensions for the Amethyst Gemini server.

The extensions in this repository are:

* **pydoc**: a Python documentation browser. No parameters.
* **redirect**: a redirect generator. Configure with:
  * `to`: base URL for redirects
  * `permanent`: boolean (default false) indicating whether to use a permanent or temporary redirect
