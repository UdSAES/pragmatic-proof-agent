#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Provide global test fixtures for unit tests.

Also, modify PATH to resolve references properly; see
https://docs.python-guide.org/writing/structure/#test-suite
for an explanation.
"""

import os
import sys

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader

BASEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV = Environment(
    loader=FileSystemLoader(BASEPATH),
    trim_blocks=True,
    lstrip_blocks=True,
)


sys.path.insert(0, BASEPATH)
import agent  # noqa -- import has to happen _after_ modifying PATH


def pytest_generate_tests(metafunc):
    """Parameterize tests by reading their consituents from a YAML-file."""

    prefixes = (
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> ."
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> ."
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> ."
        "@prefix foaf: <http://xmlns.com/foaf/spec/#> ."
        "@prefix hydra: <http://www.w3.org/ns/hydra/core#> ."
        "@prefix http: <http://www.w3.org/2011/http#> ."
        "@prefix sh: <http://www.w3.org/ns/shacl#> ."
        "@prefix qudt: <http://qudt.org/schema/qudt/> ."
        "@prefix unit: <http://qudt.org/vocab/unit/> ."
        "@prefix fmi: <https://ontologies.msaas.me/fmi-ontology.ttl#> ."
        "@prefix ex: <http://example.org/> ."
    )

    # Load questions from rendered template
    template = ENV.get_template("tests/data/rdf2http.yaml.j2")
    collection = yaml.full_load(
        template.render(
            prefixes=prefixes,
            basepath=os.path.join(BASEPATH, "tests", "data"),
        )
    )

    # Generate tests using the hook provided by pytest
    if "rdf2http" in metafunc.fixturenames:
        metafunc.parametrize("rdf2http", collection["rdf2http"])
