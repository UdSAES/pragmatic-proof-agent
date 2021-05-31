#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Initialize package."""


import os
import sys

from loguru import logger

# Configure logging
log_level = os.getenv("AGENT_LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stdout, level=log_level, diagnose=True, backtrace=False)
logger.level("REQUEST", no=15, color="<cyan><b>")  # separate level for HTTP-requests


# Expose submodule functions on top level
from .agent import correct_n3_syntax  # noqa
