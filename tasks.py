#!/usr/bin/env python3
# -*- coding: utf8 -*-

# SPDX-FileCopyrightText: 2022 UdS AES <https://www.uni-saarland.de/lehrstuhl/frey.html>
# SPDX-License-Identifier: MIT


"""Expose CLI and examples demonstrating the use of the Pragmatic Proof Algorithm."""


import os
import re
import sys

import requests
from invoke import Context, task
from jinja2 import Environment, FileSystemLoader

from agent import FAILURE, SUCCESS, logger, solve_api_composition_problem


# Utitily functions
def delete_all_files(directory):
    """Delete all files in `directory`."""

    logger.info(f"Removing all files in {directory}...")

    for file in os.scandir(directory):
        logger.debug(f"Removing file {file.path}...")
        os.remove(file.path)


def split_restdesc(text, directory):
    """Store each RESTdesc rule in a separate file.

    This facilitates handling in the pragmatic proof algorithm as omitting a rule from
    evaluation becomes trivial iff all rules are stored in a separate file.
    """

    # Extract prefix declarations
    prefixes_regex = re.compile(
        r"^(?P<prefix>@prefix) (?P<abbrv>[\w-]*:) (?P<url><[\w\d:\/\.#-]+>) *\.$",
        re.MULTILINE,
    )

    prefixes_all = ""
    for p, c, l in prefixes_regex.findall(text):
        prefixes_all += f"{p} {c} {l} .\n"

    # Get iterable for all rules in input
    rules_regex = re.compile(
        r"(?P<rule>{[.\n\s_:?\w\";\/\[\]]*}\n*=>\n*{[.\n\s_:?\w\";\/\[\]-]*\n*}\s*\.)"
    )

    # # TODO Also get corresponding comment
    # r"^#\s+[\w\s]*#*$"

    # Write each rule to disk in a separate file
    filenames = []
    rule_number = 0
    for rule in rules_regex.findall(text):
        filename = f"rule_{rule_number:0>2}.n3"
        filepath = os.path.join(directory, filename)

        logger.debug(f"Saving RESTdesc rule as '{filename}'...")
        with open(filepath, "w") as fp:
            fp.write(f"{prefixes_all}\n{rule}")

        filenames.append(filename)
        rule_number += 1

    return filenames


@task(
    help={
        "origin": "The root URL to the service instance",
        "tmp_dir": "The directory in which to store all files created during execution",
        "tmp_clean": "Delete all files in `tmp_dir` before starting",
        "selector": "Identifier for which variant of the img-API to use ('en'/'de'/'fr')",
    },
    optional=["selector"],
)
def download_restdesc(ctx, origin, tmp_dir, tmp_clean=False, selector=None):
    """
    Download RESTdesc descriptions from service instance.

    SPECIFIC TO THE EXAMPLES; NOT UNIVERSALLY VALID!
    """

    logger.info(f"Downloading RESTdesc descriptions from {origin}...")

    if tmp_clean == True:
        delete_all_files(tmp_dir)

    if selector in ["en", "de", "fr"]:
        # TODO stop this madness
        logger.warning(f"Discovery of RESTdesc hardcoded against known URI structure!")

    if selector == None:
        selector = "ms"

    api_paths = {
        "en": [
            "/images",
            "/images/_",
            "/images/_/thumbnail",
        ],
        "de": [
            "/bilder",
            "/bilder/_",
            "/bilder/_/miniaturbild",
        ],
        "fr": [
            "/photos",
            "/photos/_",
            "/photos/_/miniature",
        ],
        "ms": ["/"],
    }
    content_type = "text/n3"

    filenames = []

    for path in api_paths[selector]:
        href = f"{origin}{path}"
        headers = {"accept": content_type}

        logger.log("REQUEST", f"OPTIONS {href}")
        r = requests.options(href, headers=headers)

        restdesc = r.text
        if restdesc == "" or r.status_code == 501:
            logger.warning(f"RESTdesc for path '{path}' is empty/does not exist")
        else:
            if path == "/":
                # Store each rule in a separate file so 'R without r' works better
                filenames = split_restdesc(restdesc, tmp_dir)
            else:
                filename = "_".join(path.replace("_", "x").split("/")[1:]) + ".n3"
                logger.debug(f"{filename}\n{restdesc}")

                # Store on disk
                path = os.path.join(tmp_dir, filename)
                logger.trace(f"Writing RESTdesc to {path}...")
                with open(path, "w") as fp:
                    fp.write(restdesc)

                filenames.append(filename)

    return filenames


@task(
    help={
        "example": "The example to run: 'image-resizing' or 'simulation'",
        "origin": "The root URL to the service instance",
        "tmp_dir": "The directory in which to store all files created during execution",
        "tmp_clean": "Delete all files in `tmp_dir` before starting",
    }
)
def run_example(ctx, example, origin, tmp_dir, tmp_clean=False):
    """Collect definition of specific API composition problem; then solve it."""

    # Choose between the examples provided in this repository
    if example not in ["image-resizing", "simulation"]:
        logger.error(f"Example '{example}' not supported, exiting...")
        sys.exit(1)

    logger.info(f"Running example '{example}'...")

    # Example: Resizing an image
    if example == "image-resizing":
        selector = os.getenv("IMG_API_LANG")

        if selector == None:
            logger.error(f"ENVVAR 'IMG_API_LANG' MUST be set, exiting...")
            sys.exit(1)

        templates_dir = "./examples/image_resizing"
        input = "example.png"

        logger.debug(f"{selector=}")

    # Example: Simulation of a Functional Mockup Unit
    if example == "simulation":
        templates_dir = "./examples/simulation"
        selector = None
        input = "model.fmu"

    # Environment to be used when rendering templates using Jinja2
    ENV = Environment(
        loader=FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if tmp_clean == True:
        delete_all_files(tmp_dir)

    # Specify _initial state H_
    initial = ENV.get_template("initial_state.n3.jinja")
    H = "00_init_facts.n3"

    # Define the _goal state g_, i.e. the agent's objective
    goal = ENV.get_template("agent_goal.n3.jinja")
    g = "00_init_goal.n3"

    # Discover _description formulas R_ (RESTdesc descriptions)
    R = download_restdesc(ctx, origin, tmp_dir, False, selector)

    # Specify additional _background knowledge B_ [if applicable]
    background = ENV.get_template("background_knowledge.n3.jinja")
    B = "00_init_knowledge.n3"

    # Ensure that all relevant knowledge is stored in a file on disk
    for template, filename, data in [
        (initial, H, {"filepath": os.path.abspath(os.path.join(templates_dir, input))}),
        (goal, g, {}),
        (background, B, {}),
    ]:
        path = os.path.join(tmp_dir, filename)
        with open(path, "w") as fp:
            fp.write(template.render(data))

    # Solve API composition problem
    status = solve_api_composition_problem(ctx, tmp_dir, [H], g, R, B)

    # Properly set exit code
    if status == SUCCESS:
        logger.info("Done! ????")
    else:
        logger.error("???? Terminating with non-zero exit code...")

    sys.exit(status)
