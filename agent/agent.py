#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Software agent for hypermedia API composition and execution."""


import os
import re
import sys
from urllib.parse import urlparse

import rdflib
import requests
from invoke import task
from loguru import logger
from rdflib.plugins.sparql import prepareQuery

# Configure logging
log_level = os.getenv("AGENT_LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stdout, level=log_level, diagnose=True, backtrace=False)
logger.level("REQUEST", no=15, color="<cyan><b>")  # separate level for HTTP-requests

# Global constants/magic variables
SUCCESS = 0  # implies successful completion of an algorithm
FAILURE = 1  # implies that an algorithm failed to find a solution (_not_ an error!)


# Utitily functions
def delete_all_files(ctx, directory):
    """Delete all files in `directory`."""

    logger.info("Removing all files in $AGENT_TMP...")

    for file in os.scandir(directory):
        logger.debug(f"Removing file {file.path}...")
        os.remove(file.path)


def correct_n3_syntax(input):
    """Fix N3 syntax variants not universally supported."""

    pattern = re.compile(
        r"^(?P<prefix>PREFIX) (?P<abbrv>[\w-]+:) (?P<url><[\w:\/\.#]+>)$", re.MULTILINE
    )

    output = pattern.sub(r"@prefix \g<abbrv> \g<url>.", input)
    return output


def request_from_graph(graph):
    """Extract parts of an HTTP request from a graph."""

    http_ontology_prefix = "http://www.w3.org/2011/http#"
    http_methods = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "HEAD",
        "PATCH",
    ]  # CONNECT, OPTIONS, TRACE are not part of RESTdesc (see definition 12)

    request = None  # to be assigned later

    # Query graph for relevant information using SPARQL
    q0 = prepareQuery(
        (
            "SELECT ?method ?uri ?headers ?body "
            "WHERE { "
            "?s http:methodName ?method. "
            "?s http:requestURI ?uri. "
            "OPTIONAL { ?s http:headers ?headers. }"
            "OPTIONAL { ?s http:body ?body. }"
            "}"
        ),
        initNs={
            "http": http_ontology_prefix,
        },
    )
    a0 = graph.query(q0)

    for method_rdfterm, uri_rdfterm, headers_rdfterm, body_rdfterm in a0:
        logger.trace(
            f"\n{method_rdfterm=}\n{uri_rdfterm=}"
            f"\n{headers_rdfterm=}\n{body_rdfterm=}"
        )

        # Extract method and verify it's valid
        method = method_rdfterm.n3().strip('"')
        logger.trace(f"{method=}")

        if not (method in http_methods):
            logger.warning(f"{method=} is not an HTTP method!")
            continue

        # Check URI for completeness/distinguish from blank nodes
        url = urlparse(uri_rdfterm.n3().strip('"'))
        if url.scheme == "" or url.netloc == "":
            logger.debug(f"{url=} is incomplete, i.e. _not_ ground!")
            continue

        # TODO Prepare dictionary of headers to send
        headers = None

        # Prepare dictionary of { filename: fileobject } to send
        file_url = urlparse(body_rdfterm.n3().strip("<>"))
        file_path = file_url.path
        file_name = file_path.split("/")[-1]
        files = {file_name: file_path}

        # Create https://2.python-requests.org/en/master/api/#requests.Request-instance
        request = requests.Request(
            method=method, url=url.geturl(), headers=headers, files=files
        )

        logger.debug(
            f"Found ground request:\n{request.method} {request.url} "
            "with {request.headers=}, {request.files=}"
        )

    # TODO Verify that this also works iff there are several ground requests
    return request


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

    logger.info(f"Downloading RESTdesc descriptions from {origin}...")

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
    }  # XXX THIS IS SPECIFIC TO THE IMAGE-RESIZING EXAMPLE!!
    content_type = "text/n3"

    filenames = []

    for path in api_paths[language]:
        href = f"{origin}{path}"
        headers = {"accept": content_type}

        logger.log("REQUEST", f"OPTIONS {href}")
        r = requests.options(href, headers=headers)

        restdesc = r.text
        if restdesc == "" or r.status_code == 501:
            logger.warning(f"RESTdesc for path '{path}' is empty/does not exist")
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
    optional=["iteration", "workdir"],
    help={
        "input_files": "The filenames of all input files",
        "agent_goal": "The name of the .n3-file specifying the agent's goal",
        "iteration": "A non-negative integer used as postfix for the output files",
        "workdir": "The directory inside the container at which files are mounted",
    },
)
def eye_generate_proof(ctx, input_files, agent_goal, iteration=0, workdir="/mnt"):
    """Generate proof using containerized EYE reasoner."""

    logger.info("Generating proof using EYE...")

    # Assemble command
    dir_n3 = os.getenv("AGENT_TMP")
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

    # Generate proof
    timeout = int(os.getenv("EYE_TIMEOUT")) if os.getenv("EYE_TIMEOUT") else None
    result = ctx.run(cmd, hide=True, timeout=timeout)

    # Modify proof to ensure all parts of the stack understand the syntax
    content = correct_n3_syntax(result.stdout)

    logger.debug(f"Reasoning logs:\n{result.stderr}")
    logger.debug(f"Proof deduced by EYE:\n{content}")

    # Was the reasoner able to generate a proof?
    # FIXME A non-zero return code does not imply a proof was found!
    if result.ok:
        status = SUCCESS
    else:
        status = FAILURE

    # Store the proof as a file on disk
    proof = f"proof_{iteration:0>2}.n3"
    path = os.path.join(dir_n3, proof)
    with open(path, "w") as fp:
        fp.write(content)

    return status, path


@task(
    iterable=["R"],
    help={
        "proof": "The .n3-file containing the proof",
        "R": "The RESTdesc descriptions as .n3-files",
        "prefix": "The path of the directory in which the .n3-files are found within the container",
    },
)
def find_rule_applications(ctx, proof, R, prefix):
    """Count how many times rules of R are applied in the proof."""

    # Parse graph from n3-file
    graph = rdflib.Graph()
    graph.parse(proof, format="n3")

    # Identify applications of R in proof
    n_pre = 0
    for file in R:
        # Identify triple resulting from loading the source file containing part of R
        file_name = file.split("/")[-1]
        file_uriref = rdflib.URIRef(f"file://{prefix}/{file_name}")
        logger.debug(f"Finding applications of rules stated in '{file_name}'...")

        # Count number of triples that match SPARQL query
        q0 = prepareQuery(
            (
                "SELECT ?x ?y "
                "WHERE { "
                f"?x ?p0 {file_uriref.n3()}. "
                "?y ?p1 ?x. "
                "}"
            )
        )
        a0 = graph.query(q0)

        for x, y in a0:
            logger.trace(f"\n{x=}\n{y=}")
            n_pre += 1

    logger.trace(f"{n_pre=}")
    return n_pre


@task(
    iterable=["R"],
    help={
        "proof": "The .n3-file containing the proof",
        "R": "The RESTdesc descriptions as .n3-files",
        "prefix": "The path of the directory in which the .n3-files are found within the container",
    },
)
def identify_http_requests(ctx, proof, R, prefix):
    """Extract HTTP requests in proof resulting from R."""

    requests_ground = []

    # Read and parse entire proof from n3-file
    graph = rdflib.Graph()
    graph.parse(proof, format="n3")

    # Iterate over all files comprising R
    for file in R:
        # Construct identifier for which to search
        file_name = file.split("/")[-1]
        file_uriref = rdflib.URIRef(f"file://{prefix}/{file_name}")
        logger.debug(f"Finding applications of rules stated in '{file_name}'...")

        # Find HTTP requests that are part of the application of a rule ∈ R
        q0 = prepareQuery(
            (
                "SELECT ?a ?b ?c ?x "
                "WHERE { "
                f"?a r:source {file_uriref.n3()}. "
                "?b ?p ?a. "
                "?c r:rule ?b. "
                "?c r:gives ?x. "
                "}"
            ),
            initNs={
                "r": "http://www.w3.org/2000/10/swap/reason#",
            },
        )
        a0 = graph.query(q0)

        # Inspect { N3 expression } and extract HTTP request info
        for a, b, c, x in a0:
            logger.trace(
                (
                    "Grounded SPARQL query to find { N3 } expression:\n"
                    f"{a.n3()} r:source {file_uriref.n3()}\n"
                    f"{b.n3()} ?p       {a.n3()}\n"
                    f"{c.n3()} r:rule   {b.n3()}\n"
                    f"{c.n3()} r:gives  {x.n3()}"
                )
            )

            # Inspect individual triples (for debugging)
            for s, p, o in x:
                logger.trace(
                    f"Triple in {x.n3()}:\n{s.n3()}\n--- {p.n3()}\n----- {o.n3()}"
                )

            # Extract method and request URI
            req = request_from_graph(x)

            if req != None:
                requests_ground.append(req)

    return requests_ground


@task(
    iterable=["R"],
    optional=["B", "pre_proof", "n_pre"],
    help={
        "H": ".n3-file containing the initial state",
        "g": ".n3-file specifying the agent's goal",
        "R": "The RESTdesc descriptions as .n3-files",
        "B": ".n3-file containing background knowledge",
        "pre_proof": "The .n3-file containing the pre-proof",
        "n_pre": "The number of API operations in `pre_proof`",
        "iteration": "The iteration depth",
    },
)
def solve_api_composition_problem(
    ctx, H, g, R, B=None, pre_proof=None, n_pre=None, iteration=0
):
    """Recursively solve API composition problem."""

    logger.info(
        f"Attempting to solve API composition problem, iteration {iteration}..."
    )

    logger.debug(f"{H=}")
    logger.debug(f"{g=}")
    logger.debug(f"{R=}")
    logger.debug(f"{B=}")

    workdir = "/mnt"

    if pre_proof == None:
        input_files = []
        input_files += R
        input_files.append(H)
        if B is not None:
            input_files.append(B)

        # (1) Generate the (initial) pre-proof
        status, pre_proof = eye_generate_proof(ctx, input_files, g, iteration, workdir)
        if status == FAILURE:
            return FAILURE

        # (1b) How many times are rules of R applied (i.e. how many API operations)?
        n_pre = find_rule_applications(ctx, pre_proof, R, workdir)
        logger.debug(f"{n_pre=}")

    # (2) What does `n_pre` imply?
    if n_pre == 0:
        return SUCCESS

    # TODO (3) Which HTTP requests are sufficiently specified? -> select one

    # TODO (4) Execute HTTP request

    # TODO (4) Parse response, add to ground formulas (initial state)

    # TODO (5) Generate post-proof

    # TODO (6) What is the value of `n_post`?
    # n_post = ...

    # (7) What do the values of `n_pre` and `n_post` imply?
    iteration += 1
    if n_post >= n_pre:
        status = solve_api_composition_problem(ctx, H, g, R, B, None, None, iteration)
        return status
    else:
        n_pre = n_post
        status = solve_api_composition_problem(
            ctx, H, g, R, B, pre_proof, n_pre, iteration
        )
        return status


@task(
    help={
        "image": "The full path of the image for which to obtain a thumbnail",
        "origin": "The root URL to the service instance",
        "directory": "The directory in which to store the .n3-files",
        "clean_tmp": "Set iff all files in $AGENT_TMP shall be deleted first",
    }
)
def get_thumbnail(ctx, image, origin, directory, clean_tmp=False):
    """Collect definition of API composition problem."""

    if clean_tmp == True:
        delete_all_files(ctx, directory)

    # Specify _initial state H_
    input_file = image
    initial_state = (
        "@prefix dbpedia: <http://dbpedia.org/resource/>.\n"
        "\n"
        f"<{input_file}> a dbpedia:Image.\n"
    )  # XXX THIS IS SPECIFIC TO THE IMAGE-RESIZING EXAMPLE!!
    H = "agent_knowledge.n3"

    # Define the _goal state g_, i.e. the agent's objective
    goal_state = (
        "@prefix dbpedia-owl: <http://dbpedia.org/ontology/>.\n"
        "\n"
        "{ <" + input_file + "> dbpedia-owl:thumbnail ?thumbnail. }\n"
        "=>\n"
        "{ <" + input_file + "> dbpedia-owl:thumbnail ?thumbnail. }.\n"
    )  # XXX THIS IS SPECIFIC TO THE IMAGE-RESIZING EXAMPLE!!
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
    status = solve_api_composition_problem(ctx, H, g, R, B)

    # Properly set exit code
    if status == SUCCESS:
        logger.info("Done!")
    else:
        logger.error("Terminating with non-zero exit code...")

    sys.exit(status)
