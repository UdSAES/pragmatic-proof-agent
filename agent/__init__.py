#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Initialize package."""


import os
import sys

# Expose submodule functions on top level
from .agent import correct_n3_syntax  # noqa
from .agent import identify_http_requests  # noqa
from .agent import request_from_graph  # noqa
