#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Software agent for hypermedia API composition and execution."""

from invoke import task
from loguru import logger


# Add separate log level for HTTP-requests
logger.level("REQUEST", no=15, color="<cyan><b>")


@task(help={"origin": "The root URL to the service instance"})
def discover_restdesc(ctx, origin):
    """Discover RESTdesc descriptions of service instance."""


def eye_generate_proof(inputs):
    """Generate proof using containerized EYE reasoner."""


def solve_api_composition_problem(H, g, R, B):
    """Solve API composition problem."""


def solve_task():
    """Collect definition of API composition problem."""
