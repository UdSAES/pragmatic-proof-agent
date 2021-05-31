#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Provide global test fixtures for unit tests.

Also, modify PATH to resolve references properly; see
https://docs.python-guide.org/writing/structure/#test-suite
for an explanation.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import agent  # noqa -- import has to happen _after_ modifying PATH
