#!/usr/bin/env python3
# -*- coding: utf8 -*-

# SPDX-FileCopyrightText: 2022 UdS AES <https://www.uni-saarland.de/lehrstuhl/frey.html>
# SPDX-License-Identifier: MIT


"""Initialize package."""


import os
import sys

from loguru import logger

# Expose submodule functions on top level
from .agent import (  # noqa
    FAILURE,
    SUCCESS,
    correct_n3_syntax,
    identify_http_requests,
    request_from_graph,
    solve_api_composition_problem,
)

# Configure logging
log_level = os.getenv("AGENT_LOG_LEVEL", "INFO")
logger.remove()
logger.level("DETAIL", no=15, color="<blue><b>")  # separate level for details
logger.level(
    "REQUEST", no=25, color="<fg #F063E9><b>"
)  # separate level for HTTP-requests
logger.level(
    "USER", no=25, color="<magenta><b>"
)  # separate level for (fake) user input
logger.add(sys.stdout, level=log_level, diagnose=True, backtrace=False)
