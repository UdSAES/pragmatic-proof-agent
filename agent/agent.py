#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Software agent for hypermedia API composition and execution."""


import os
import re
from urllib.parse import urlparse

import rdflib
import requests
from invoke import task
from loguru import logger
from rdflib.namespace import OWL, RDF, NamespaceManager

from . import logger

# Global constants/magic variables
SUCCESS = 0  # implies successful completion of an algorithm
FAILURE = 1  # implies that an algorithm failed to find a solution (_not_ an error!)

# Use namespace manager to enforce consistent prefixes
# https://rdflib.readthedocs.io/en/latest/namespaces_and_bindings.html
# --""--/apidocs/rdflib.html#rdflib.namespace.NamespaceManager
HTTP = rdflib.Namespace("http://www.w3.org/2011/http#")

NAMESPACE_MANAGER = NamespaceManager(rdflib.Graph())

# FIXME read prefixes/namespaces from files instead of hardcoding?
NAMESPACE_MANAGER.bind("rdf", RDF)
NAMESPACE_MANAGER.bind("owl", OWL)
NAMESPACE_MANAGER.bind("http", HTTP)
NAMESPACE_MANAGER.bind("r", rdflib.Namespace("http://www.w3.org/2000/10/swap/reason#"))
NAMESPACE_MANAGER.bind("ex", rdflib.Namespace("http://example.org/image#"))  # XXX

# Compare https://rdflib.readthedocs.io/en/stable/plugin_parsers.html (both incomplete!)
RDFLIB_SERIALIZATIONS = [
    "application/ld+json",
    "application/n-triples",
    "application/n-quads",
    "application/rdf+xml",
    "application/trig",
    "text/n3",
    "text/turtle",
    "text/html",
]


# Utitily functions
def correct_n3_syntax(input):
    """Fix N3 syntax variants not universally supported."""

    pattern = re.compile(
        r"^(?P<prefix>PREFIX) (?P<abbrv>[\w-]*:) (?P<url><[\w\d:\/\.#-]+>)$",
        re.MULTILINE,
    )

    output = pattern.sub(r"@prefix \g<abbrv> \g<url>.", input)
    return output


def request_from_graph(graph):
    """Extract parts of an HTTP request from a graph."""

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
    a0 = graph.query(
        (
            "SELECT ?method ?uri ?headers ?body "
            "WHERE { "
            "?s http:methodName ?method. "
            "?s http:requestURI ?uri. "
            "OPTIONAL { ?s http:headers ?headers. }"
            "OPTIONAL { ?s http:body ?body. }"
            "}"
        )
    )

    for method_rdfterm, uri_rdfterm, headers_rdfterm, body_rdfterm in a0:
        logger.trace(
            f"\n{method_rdfterm=}\n{uri_rdfterm=}"
            f"\n{headers_rdfterm=}\n{body_rdfterm=}"
        )

        # Extract method and verify it's valid
        method = method_rdfterm.n3().strip('"')
        logger.trace(f"{method=}")

        if not (method in http_methods):
            logger.warning(f"{method=} is not a supported HTTP method!")
            continue

        # Check URI for completeness/distinguish from blank nodes
        url = urlparse(uri_rdfterm.n3().strip('<">'))

        if url.scheme == "" or url.netloc == "":
            logger.log("DETAIL", f"{url=} is incomplete, i.e. _not_ ground!")
            continue

        # Prepare dictionary of headers to send
        headers = None
        serialization_desired = None
        if headers_rdfterm is not None:
            headers = {}
            a1 = graph.query(
                (
                    "SELECT ?fieldName ?fieldValue "
                    "WHERE { "
                    f"?r http:headers {headers_rdfterm.n3()} ."
                    f"{headers_rdfterm.n3()} http:fieldName ?fieldName ."
                    f"{headers_rdfterm.n3()} http:fieldValue ?fieldValue ."
                    "}"
                )
            )
            for k, v in a1:
                key = k.n3().strip("\"'").lower()
                value = v.n3().strip("\"'")

                headers[key] = value

        # Prepare body to send
        body = None
        if body_rdfterm is not None:
            non_parseable = False
            body_url = urlparse(body_rdfterm.n3().strip("<>"))

            if body_url.scheme == "file":
                raw = rdflib.Graph()
                filtered = rdflib.Graph()
                try:
                    raw.parse(body_url.path)

                    if body_url.fragment != "":
                        filtered = raw  # XXX only send relevant subgraph
                    else:
                        filtered = raw
                except Exception:
                    non_parseable = True

                if non_parseable == False:
                    media_type = (
                        serialization_desired
                        if (
                            serialization_desired != None
                            and serialization_desired in RDFLIB_SERIALIZATIONS
                        )
                        else "text/turtle"
                    )
                    body = filtered.serialize(format=media_type)

                    if headers == None:
                        headers = {}
                    headers["content-type"] = media_type

                    # Work around https://github.com/RDFLib/rdflib/issues/677
                    body = body.replace(f"file://{body_url.path}", "")
                else:
                    with open(body_url.path, "rb") as fp:
                        body = fp.read()
                    headers["content-type"] = "application/octet-stream"
            else:
                raise NotImplementedError

        # TODO Prepare other request parts
        files = None
        params = None
        auth = None
        cookies = None

        # Instantiate https://docs.python-requests.org/en/latest/api/#requests.Request
        request = requests.Request(
            method=method,
            url=url.geturl(),
            headers=headers,
            files=files,
            data=body,
            params=params,
            auth=auth,
            cookies=cookies,
        )

        logger.log(
            "DETAIL",
            f"Found ground request:\n{request.method} {request.url} "
            f"with {request.headers=}, {request.files=}",
        )

    return request


def concatenate_eye_input_files(H, g, R, B=None):
    logger.log("DETAIL", f"{H=}")
    logger.log("DETAIL", f"{g=}")
    logger.log("DETAIL", f"{R=}")
    logger.log("DETAIL", f"{B=}")

    input_files = []
    input_files += R
    input_files += H
    if B is not None:
        input_files.append(B)

    return input_files


# Core functionality
# http://docs.pyinvoke.org/en/stable/concepts/invoking-tasks.html#iterable-flag-values
@task(
    iterable=["input_files"],
    optional=["suffix", "workdir"],
    help={
        "input_files": "The filenames of all input files",
        "agent_goal": "The name of the .n3-file specifying the agent's goal",
        "suffix": "A suffix for the file name in which the proof is stored",
        "workdir": "The directory inside the container at which files are mounted",
    },
)
def eye_generate_proof(ctx, input_files, agent_goal, suffix=None, workdir="/mnt"):
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
    graph = rdflib.Graph()
    graph.namespace_manager = NAMESPACE_MANAGER
    graph.parse(data=content, format="n3")

    if result.ok and (len(graph) > 0):
        status = SUCCESS
    else:
        logger.error("EYE was unable to generate a proof, halting with FAILURE!")
        status = FAILURE

    # Store the proof as a file on disk
    proof = "proof.n3" if suffix is None else f"proof_{suffix}.n3"
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

    logger.info("Counting how many times rules of R are applied in the proof...")

    # Parse graph from n3-file
    graph = rdflib.Graph()
    graph.namespace_manager = NAMESPACE_MANAGER
    graph.parse(proof, format="n3")

    # Identify applications of R in proof
    n_pre = 0
    for file in R:
        # Identify triple resulting from loading the source file containing part of R
        file_name = file.split("/")[-1]
        file_uriref = rdflib.URIRef(f"file://{prefix}/{file_name}")
        logger.log(
            "DETAIL", f"Finding applications of rules stated in '{file_name}'..."
        )

        # Count number of triples that match SPARQL query
        a0 = graph.query(
            (
                "SELECT ?x ?y "
                "WHERE { "
                f"?x ?p0 {file_uriref.n3()}. "
                "?y ?p1 ?x. "
                "}"
            )
        )

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

    logger.info("Extracting ground HTTP requests in proof resulting from R...")

    requests_ground = []

    # Read and parse entire proof from n3-file
    graph = rdflib.Graph()
    graph.namespace_manager = NAMESPACE_MANAGER
    graph.parse(proof, format="n3")

    # Iterate over all files comprising R
    for file in R:
        # Construct identifier for which to search
        file_name = file.split("/")[-1]
        file_uriref = rdflib.URIRef(f"file://{prefix}/{file_name}")
        logger.log(
            "DETAIL", f"Finding applications of rules stated in '{file_name}'..."
        )

        # Find HTTP requests that are part of the application of a rule ∈ R
        a0 = graph.query(
            (
                "SELECT ?a ?b ?c ?x "
                "WHERE { "
                f"?a r:source {file_uriref.n3()}. "
                "?b ?p ?a. "
                "?c r:rule ?b. "
                "?c r:gives ?x. "
                "}"
            )
        )

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
            x.namespace_manager = NAMESPACE_MANAGER
            req = request_from_graph(x)

            if req != None:
                requests_ground.append((file, req))

    return requests_ground


def parse_http_body(node, r):
    """Parse triples about a HTTP message body."""

    triples = []

    # Identify MIME type of the message body
    try:
        content_type_parts = r.headers["content-type"].split(";")
    except KeyError:
        logger.warning(
            f"{r=} doesn't have a 'content-type'-header, "
            "aborting attempt to parse body..."
        )
        return triples

    content_type = content_type_parts[0]
    content_type_type = content_type.split("/")[0]
    content_type_subtype = content_type.split("/")[1]

    if len(content_type_parts) == 2:
        content_type_parameter = content_type_parts[1]

    message_type = "response" if isinstance(r, requests.Response) else "request"
    logger.log(
        "DETAIL", f"The MIME type for the HTTP {message_type} is '{content_type}'"
    )

    # Determine whether or not the message body is binary file
    if (content_type_type in ["audio", "image", "video"]) or (
        content_type == "application/octet-stream"
    ):
        content_is_binary = True
    elif (
        (content_type_type in ["text"])
        or ("json" in content_type_subtype)
        or ("xml" in content_type_subtype)
        or (
            content_type
            in ["application/n-triples", "application/n-quads", "application/trig"]
        )
    ):
        content_is_binary = False
    elif content_type == "multipart/form-data":
        content_is_binary = True  # TODO assume binary content for now
        logger.warning(
            f"Parsing triples about 'multipart/form-data'-{message_type}s is not yet "
            "implemented!"
        )  # TODO
    else:
        content_is_binary = True
        logger.warning(
            f"Don't know whether or not '{content_type}' is binary -> assuming it is!"
        )

    if not content_is_binary:
        if content_type in RDFLIB_SERIALIZATIONS:
            # Parse triples from non-binary message body
            if isinstance(r, requests.Response):
                data = r.text
            else:
                data = r.body
            r_body_ds = rdflib.Dataset()
            r_body_ds.namespace_manager = NAMESPACE_MANAGER
            r_body_ds.parse(data=data, format=content_type, publicID=r.url)

            for graph in r_body_ds.graphs():
                for s, p, o in graph:
                    triples.append((s, p, o))
                    triples.append((node, HTTP.body, s))

            r_body_serialized = r_body_ds.serialize(format="application/trig")
            logger.trace(f"Triples parsed from message body:\n{r_body_serialized}")
        else:
            logger.warning(
                f"Found unsupported non-binary content-type '{content_type}'; "
                "won't attempt to parse that!"
            )
    else:
        # TODO Parse triples off of binary content?
        logger.error("Parsing triples off of binary content not implemented yet!")

    return triples


def parse_http_response(response):
    """Extract all triples from HTTP response object."""

    logger.info("Extracting new information from HTTP request/response...")

    # Prepare for parsing
    request = response.request
    triples = []

    # Create new individual which becomes the subject of all triples
    request_node = rdflib.BNode()  # identifier for the request
    response_node = rdflib.BNode()  # identifier for the response

    # Parse triples about the request method
    triples.append((request_node, HTTP.Method, rdflib.Literal(request.method)))

    # Parse triples about the request URL
    triples.append((request_node, HTTP.requestURI, rdflib.URIRef(request.url)))

    # Parse triples about the request headers
    for name, value in request.headers.items():
        header_bnode = rdflib.BNode()
        triples.append((header_bnode, RDF.type, HTTP.ResponseHeader))
        triples.append((header_bnode, HTTP.fieldName, rdflib.Literal(name)))
        triples.append((header_bnode, HTTP.fieldValue, rdflib.Literal(value)))

        triples.append((request_node, HTTP.headers, header_bnode))

    # Parse triples about the request body
    triples += parse_http_body(request_node, request)

    # Parse triples about the response status
    triples.append(
        (response_node, HTTP.statusCodeNumber, rdflib.Literal(response.status_code))
    )
    triples.append((response_node, HTTP.reasonPhrase, rdflib.Literal(response.reason)))

    # Parse triples about the response headers
    for name, value in response.headers.items():
        header_bnode = rdflib.BNode()
        triples.append((header_bnode, RDF.type, HTTP.ResponseHeader))
        triples.append((header_bnode, HTTP.fieldName, rdflib.Literal(name)))
        triples.append((header_bnode, HTTP.fieldValue, rdflib.Literal(value)))

        triples.append((response_node, HTTP.headers, header_bnode))

    # Parse response body according to its (hyper-)media type
    triples += parse_http_body(response_node, response)

    # Connect response to request
    triples.append((request_node, RDF.type, HTTP.Request))
    triples.append((response_node, RDF.type, HTTP.Response))
    triples.append((request_node, HTTP.resp, response_node))

    return triples


@task(
    iterable=["H", "R"],
    optional=["B", "pre_proof", "n_pre"],
    help={
        "H": ".n3-files containing the initial state",
        "g": ".n3-file specifying the agent's goal",
        "R": "The RESTdesc descriptions as .n3-files",
        "B": ".n3-file containing background knowledge",
        "pre_proof": "The .n3-file containing the pre-proof",
        "n_pre": "The number of API operations in `pre_proof`",
        "iteration": "The iteration depth",
    },
)
def solve_api_composition_problem(
    ctx, directory, H, g, R, B=None, pre_proof=None, n_pre=None, iteration=0
):
    """Recursively solve API composition problem."""

    logger.info(
        f"Attempting to solve API composition problem, iteration {iteration}..."
    )

    workdir = "/mnt"

    input_files = concatenate_eye_input_files(H, g, R, B)

    if pre_proof == None:
        # (1) Generate the (initial) pre-proof
        status, pre_proof = eye_generate_proof(
            ctx, input_files, g, f"{iteration:0>2}_pre", workdir
        )
        if status == FAILURE:
            return FAILURE

        # (1b) How many times are rules of R applied (i.e. how many API operations)?
        n_pre = find_rule_applications(ctx, pre_proof, R, workdir)
        logger.log("DETAIL", f"{n_pre=}")

    # (2) What does `n_pre` imply?
    if n_pre == 0:
        logger.success(
            f"🎉 The pragmatic proof algorithm terminated successfully since {n_pre=}!"
        )
        return SUCCESS

    # (3) Which HTTP requests are sufficiently specified? -> select one
    ground_requests = identify_http_requests(ctx, pre_proof, R, workdir)
    r, request_object = ground_requests[0]

    # (4) Execute HTTP request
    logger.log("REQUEST", f"{request_object.method} {request_object.url}")

    request_prepared = request_object.prepare()
    session = requests.Session()
    response_object = session.send(request_prepared)

    # (4) Parse response, add to ground formulas (initial state)
    response_triples = parse_http_response(response_object)

    response_graph = rdflib.Graph()
    response_graph.namespace_manager = NAMESPACE_MANAGER

    for s, p, o in response_triples:
        response_graph.add((s, p, o))

    # Write newly gained knowledge to disk
    response_graph_serialized = response_graph.serialize(format="n3")
    logger.debug(f"New information parsed from response:\n{response_graph_serialized}")

    G = f"knowledge_gained_{iteration:0>2}.n3"

    with open(os.path.join(directory, G), "w") as fp:
        fp.write(response_graph_serialized)

    # (5a) Update agent knowledge by creating union of sets H and G; write to disk
    # FIXME should this be a merge or the set operation G1 + G2??
    H_union_G = rdflib.Graph()
    H_union_G.namespace_manager = NAMESPACE_MANAGER
    H_union_G.parse(os.path.join(directory, H[0]), format="n3")
    H_union_G.parse(os.path.join(directory, G), format="n3")

    agent_knowledge_updated = H_union_G.serialize(format="n3")
    logger.debug(f"agent_knowledge_updated:\n{agent_knowledge_updated}")

    agent_knowledge = f"agent_knowledge_{iteration:0>2}_post.n3"

    with open(os.path.join(directory, agent_knowledge), "w") as fp:
        fp.write(agent_knowledge_updated)

    # (5b) Generate post-proof
    input_files = concatenate_eye_input_files([agent_knowledge], g, R, B)
    status, post_proof = eye_generate_proof(
        ctx, input_files, g, f"{iteration:0>2}_post", workdir
    )

    # (6) What is the value of `n_post`?
    if status == FAILURE:
        n_post = n_pre
    else:
        n_post = find_rule_applications(ctx, post_proof, R, workdir)

    logger.log("DETAIL", f"{n_pre=}; {n_post=}")

    # (7) What do the values of `n_pre` and `n_post` imply?
    iteration += 1
    if n_post >= n_pre:
        R_difference_r = [x for x in R if not x == r]
        status = solve_api_composition_problem(
            ctx, directory, H, g, R_difference_r, B, None, None, iteration
        )
        return status
    else:
        n_pre = n_post
        status = solve_api_composition_problem(
            ctx, directory, H, g, R, B, post_proof, n_pre, iteration
        )
        return status
