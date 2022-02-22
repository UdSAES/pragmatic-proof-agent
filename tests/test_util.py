#!/usr/bin/env python3
# -*- coding: utf8 -*-

# SPDX-FileCopyrightText: 2022 UdS AES <https://www.uni-saarland.de/lehrstuhl/frey.html>
# SPDX-License-Identifier: MIT


"""Unit tests for utitily functions."""

import os

import invoke
import pytest
import rdflib
import requests

import agent

test_data_base_path = os.path.normpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "data")
)


class TestUtitityFunctions(object):
    @pytest.mark.parametrize(
        "input, expected",
        [
            (
                "PREFIX dbpedia: <http://dbpedia.org/resource/>",
                "@prefix dbpedia: <http://dbpedia.org/resource/>.",
            ),
            (
                "PREFIX dbpedia-owl: <http://dbpedia.org/ontology/>",
                "@prefix dbpedia-owl: <http://dbpedia.org/ontology/>.",
            ),
            (
                "PREFIX : <http://localhost:4000/models/6157f34f-f629-484b-b873-f31be22269e1#>",
                "@prefix : <http://localhost:4000/models/6157f34f-f629-484b-b873-f31be22269e1#>.",
            ),
            (
                "PREFIX ex: <http://example.org/image#>",
                "@prefix ex: <http://example.org/image#>.",
            ),
            (
                (
                    "PREFIX http: <http://www.w3.org/2011/http#>\n"
                    "PREFIX r: <http://www.w3.org/2000/10/swap/reason#>"
                ),
                (
                    "@prefix http: <http://www.w3.org/2011/http#>.\n"
                    "@prefix r: <http://www.w3.org/2000/10/swap/reason#>."
                ),
            ),
        ],
    )
    def test_correct_n3_syntax(self, input, expected):
        actual = agent.correct_n3_syntax(input)

        assert actual == expected

    def test_request_from_graph(self, rdf2http):
        graph = rdflib.Graph()
        graph.parse(data=rdf2http["graph"], format="text/turtle")

        actual = agent.request_from_graph(graph, None)

        assert actual.url == rdf2http["expected"]["url"]
        assert actual.method == rdf2http["expected"]["method"]
        assert actual.params == rdf2http["expected"]["params"]
        assert actual.headers == rdf2http["expected"]["headers"]
        if rdf2http["expected"]["body"] != None:
            assert actual.body == rdf2http["expected"]["body"]
        if rdf2http["expected"]["files"] != None:
            assert actual.files == rdf2http["expected"]["files"]

    @pytest.mark.skip(reason="Relies on hardcoded paths in `00_pre_proof.n3`, to be resolved")
    @pytest.mark.parametrize(
        "proof, R, prefix, expected",
        [
            (
                os.path.join(test_data_base_path, "00_pre_proof.n3"),
                [
                    os.path.join(test_data_base_path, "images.n3"),
                    os.path.join(test_data_base_path, "images_x_thumbnail.n3"),
                ],
                "/mnt",
                [
                    requests.Request(
                        "POST",
                        "http://example.com/images",
                        headers={
                            "accept": "text/n3",
                            "content-type": "application/octet-stream",
                        },
                        data=os.path.join(test_data_base_path, "example.png"),
                    )
                ],
            )
        ],
    )
    def test_identify_http_requests(self, proof, R, prefix, expected):
        ctx = invoke.context.Context()  # empty context

        results = agent.identify_http_requests(ctx, proof, R, prefix, rdflib.Graph())

        assert len(results) == len(expected)

        for index, result in enumerate(results):
            with open(expected[index].data, "rb") as fp:
                expected[index].data = fp.read()

            r, actual = result
            assert actual.method == expected[index].method
            assert actual.url == expected[index].url
            assert actual.headers == expected[index].headers
            assert actual.data == expected[index].data
