#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Initialize package."""


import os
import sys

from loguru import logger

# Expose submodule functions on top level
from .agent import FAILURE, SUCCESS, solve_api_composition_problem  # noqa

# Configure logging
log_level = os.getenv("AGENT_LOG_LEVEL", "INFO")
logger.remove()
logger.level("DETAIL", no=15, color="<blue><b>")  # separate level for details
logger.level("REQUEST", no=25, color="<cyan><b>")  # separate level for HTTP-requests
logger.add(sys.stdout, level=log_level, diagnose=True, backtrace=False)
