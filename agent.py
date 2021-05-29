#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Software agent for hypermedia API composition and execution."""


import os

import requests
from invoke import task
from loguru import logger


# Add separate log level for HTTP-requests
logger.level("REQUEST", no=15, color="<cyan><b>")

# Utitily functions
def delete_all_files(ctx, directory):
    """Delete all files in `directory`."""

    for file in os.scandir(directory):
        logger.debug(f"Removing file {file.path}...")
        os.remove(file.path)


# Core functionality
@task(
    help={
        "origin": "The root URL to the service instance",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def download_restdesc(ctx, origin, directory, clean_tmp=False):
    """Download RESTdesc descriptions of service instance."""

    if clean_tmp == True:
        delete_all_files(ctx, directory)

    logger.warning(f"Discovery of RESTdesc is hardcoded against known URI structure!")

    language = os.getenv("IMG_API_LANG", "en")
    logger.debug(f"Selected language '{language}'")

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
    }
    content_type = "text/n3"

    filenames = []

    for path in api_paths[language]:
        href = f"{origin}{path}"
        headers = {"accept": content_type}

        logger.log("REQUEST", f"OPTIONS {href}")
        r = requests.options(href, headers=headers)

        restdesc = r.text
        if restdesc == "":
            logger.warning(f"RESTdesc for path '{path}' is empty")
        else:
            filename = "_".join(path.replace("_", "x").split("/")[1:]) + ".n3"
            logger.debug(f"{filename}\n{restdesc}")

            logger.debug(f"Writing RESTdesc to {path}...")
            path = os.path.join(directory, filename)
            with open(path, "w") as fp:
                fp.write(restdesc)

            filenames.append(filename)

    return filenames


# http://docs.pyinvoke.org/en/stable/concepts/invoking-tasks.html#iterable-flag-values
@task(
    iterable=["input_files"],
    help={
        "input_files": "The filenames of all input files",
        "agent_goal": "The name of the .n3-file specifying the agent's goal",
    },
)
def eye_generate_proof(ctx, input_files, agent_goal):
    """Generate proof using containerized EYE reasoner."""

    logger.info("Generating proof using EYE...")

    dir_n3 = os.getenv("AGENT_TMP")
    workdir = "/mnt"
    image_name = os.getenv("EYE_IMAGE_NAME")
    prefix = (
        "docker run "
        "-i "
        "--rm "
        "--name eye "
        f"-v {dir_n3}:{workdir} "
        f"-w {workdir} "
        f"{image_name} "
    )

    options = "--quiet --tactic limited-answer 1"
    filenames = " ".join(input_files)
    cmd_container = f"{options} {filenames} --query {agent_goal}"

    cmd = prefix + cmd_container
    logger.debug(cmd)

    result = ctx.run(cmd, hide=True)

    logger.debug(f"Reasoning logs:\n{result.stderr}")
    logger.debug(f"Proof deduced by EYE:\n{result.stdout}")


@task(
    iterable=["R"],
    optional=["B"],
    help={
        "H": ".n3-file containing the initial state",
        "g": ".n3-file specifying the agent's goal",
        "R": "The RESTdesc descriptions as .n3-files",
        "B": ".n3-file containing background knowledge",
    },
)
def solve_api_composition_problem(ctx, H, g, R, B=None):
    """Solve API composition problem."""

    logger.debug(f"{H=}")
    logger.debug(f"{g=}")
    logger.debug(f"{R=}")
    logger.debug(f"{B=}")

    input_files = []
    input_files += R
    input_files.append(H)
    if B is not None:
        input_files.append(B)

    eye_generate_proof(ctx, input_files, g)


@task(
    help={
        "origin": "The root URL to the service instance",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def solve_task(ctx, origin, directory, clean_tmp=False):
    """Collect definition of API composition problem."""

    if clean_tmp == True:
        delete_all_files(ctx, directory)

    # Specify _initial state H_
    initial_state = (
        "@prefix dbpedia: <http://dbpedia.org/resource/>.\n"
        "\n"
        "<proof.png> a dbpedia:Image.\n"
    )
    H = "agent_knowledge.n3"

    # Define the _goal state g_, i.e. the agent's objective
    goal_state = (
        "@prefix dbpedia-owl: <http://dbpedia.org/ontology/>.\n"
        "\n"
        "{ <proof.png> dbpedia-owl:thumbnail ?thumbnail. }\n"
        "=>\n"
        "{ <proof.png> dbpedia-owl:thumbnail ?thumbnail. }.\n"
    )
    g = "agent_goal.n3"

    # Store initial state and the agent's goal as .n3 files on disk
    for content, filename in [(initial_state, H), (goal_state, g)]:
        path = os.path.join(directory, filename)
        with open(path, "w") as fp:
            fp.write(content)

    # Discover _description formulas R_ (RESTdesc descriptions)
    R = download_restdesc(ctx, origin, directory, False)

    # Specify additional _background knowledge B_ [if applicable]
    B = None

    # Solve API composition problem
    solve_api_composition_problem(ctx, H, g, R, B)
