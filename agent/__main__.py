#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Examples demonstrating the use of the Pragmatic Proof Algorithm."""


import os
import re
import sys

import rdflib
import requests
from invoke import Context, task
from jinja2 import Environment, FileSystemLoader

from . import FAILURE, SUCCESS, logger, solve_api_composition_problem


# Utitily functions
def delete_all_files(directory):
    """Delete all files in `directory`."""

    logger.info(f"Removing all files in {directory}...")

    for file in os.scandir(directory):
        logger.debug(f"Removing file {file.path}...")
        os.remove(file.path)


def split_restdesc(text, directory):
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
        "selector": "Identifier for which API to use ('en'/'de'/'fr'/'ms').",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def download_restdesc(ctx, origin, selector, directory, clean_tmp=False):
    """
    Download RESTdesc descriptions of service instance.

    SPECIFIC TO THE EXAMPLES; NOT UNIVERSALLY VALID!
    """

    logger.info(f"Downloading RESTdesc descriptions from {origin}...")

    if clean_tmp == True:
        delete_all_files(directory)

    if selector in ["en", "de", "fr"]:
        logger.warning(f"Discovery of RESTdesc hardcoded against known URI structure!")

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
                filenames = split_restdesc(restdesc, directory)
            else:
                filename = "_".join(path.replace("_", "x").split("/")[1:]) + ".n3"
                logger.debug(f"{filename}\n{restdesc}")

                # Store on disk
                path = os.path.join(directory, filename)
                logger.trace(f"Writing RESTdesc to {path}...")
                with open(path, "w") as fp:
                    fp.write(restdesc)

                filenames.append(filename)

    return filenames


@task(
    help={
        "origin": "The root URL to the service instance",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def get_thumbnail(ctx, origin, directory, clean_tmp=False):
    """
    Collect definition of specific API composition problem; then solve it.

    This function is specific to the image-resizing example as it should be. The rest of
    the code should be independent of any specific example, i.e. implement a generic
    (maybe even somewhat intelligent) agent!
    """

    # Environment to be used when rendering templates using Jinja2
    ENV = Environment(
        loader=FileSystemLoader("examples/image_resizing"),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if clean_tmp == True:
        delete_all_files(directory)

    # Specify _initial state H_
    initial_state = ENV.get_template("initial_state.n3.jinja")
    H = "agent_knowledge.n3"

    # Define the _goal state g_, i.e. the agent's objective
    goal_state = ENV.get_template("agent_goal.n3.jinja")
    g = "agent_goal.n3"

    # Store initial state and the agent's goal as .n3 files on disk
    # image_rdfterm = rdflib.Literal("example.png")  # XXX is hardcoding a good idea? No!
    image_rdfterm = rdflib.URIRef(
        "https://ontologies.msaas.me/example.ttl#example.png"
    )  # XXX is hardcoding a good idea? No!
    for template, filename in [(initial_state, H), (goal_state, g)]:
        path = os.path.join(directory, filename)
        with open(path, "w") as fp:
            fp.write(template.render(image=image_rdfterm.n3()))

    # Discover _description formulas R_ (RESTdesc descriptions)
    language = os.getenv("IMG_API_LANG", "en")
    logger.debug(f"Selected language '{language}'")

    R = download_restdesc(ctx, origin, language, directory, False)

    # Specify additional _background knowledge B_ [if applicable]
    B = None

    # Solve API composition problem
    status = solve_api_composition_problem(ctx, directory, [H], g, R, B)

    # Properly set exit code
    if status == SUCCESS:
        logger.info("Done! 😎")
    else:
        logger.error("💥 Terminating with non-zero exit code... ")

    sys.exit(status)


@task(
    help={
        "origin": "The root URL to the service instance",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def simulate_model(ctx, origin, directory, clean_tmp=False):
    """Collect definition of specific API composition problem; then solve it."""

    # Environment to be used when rendering templates using Jinja2
    ENV = Environment(
        loader=FileSystemLoader("examples/simulation"),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if clean_tmp == True:
        delete_all_files(directory)

    # Specify _initial state H_
    initial = ENV.get_template("initial_state.n3.jinja")
    H = "00_init_facts.n3"

    # Define the _goal state g_, i.e. the agent's objective
    goal = ENV.get_template("agent_goal.n3.jinja")
    g = "00_init_goal.n3"

    # Discover _description formulas R_ (RESTdesc descriptions)
    selector = "ms"
    R = download_restdesc(ctx, origin, selector, directory, False)

    # Make user input available in working directory
    U = [
        (
            ENV.get_template("parameters_01.n3.jinja"),
            "parameters_01.n3",
            {"filepath": os.path.join(directory, "parameters_01.n3")},
        )
    ]

    # Specify additional _background knowledge B_ [if applicable]
    background = ENV.get_template("background_knowledge.n3.jinja")
    parameter_sets = [os.path.join(directory, x[1] + "#parameters") for x in U]
    B = "00_init_knowledge.n3"

    # Ensure that all relevant knowledge is stored in a file on disk
    for template, filename, data in [
        (initial, H, {}),
        (goal, g, {}),
        (background, B, {"parameter_sets": parameter_sets}),
    ] + U:
        path = os.path.join(directory, filename)
        with open(path, "w") as fp:
            fp.write(template.render(data))

    # Solve API composition problem
    status = solve_api_composition_problem(ctx, directory, [H], g, R, B)

    # Properly set exit code
    if status == SUCCESS:
        logger.info("Done! 😎")
    else:
        logger.error("💥 Terminating with non-zero exit code...")

    sys.exit(status)


if __name__ == "__main__":

    origin = os.getenv("API_ORIGIN")
    directory = os.getenv("AGENT_TMP")
    clean_tmp = True

    simulate_model(Context(), origin, directory, clean_tmp)
