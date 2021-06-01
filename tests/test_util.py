#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Unit tests for utitily functions."""

import os
import re
import urllib

import invoke
import pytest
import requests

import agent


class TestUtitityFunctions(object):
    origin = os.environ["IMG_API_ORIGIN"]
    tmpdir = os.environ["AGENT_TMP"]

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

    @pytest.mark.parametrize(
        "proof, R, prefix, expected",
        [
            (
                f"{tmpdir}/proof_00.n3",
                [
                    f"{tmpdir}/images.n3",
                    f"{tmpdir}/images_x_thumbnail.n3",
                ],
                "/mnt",
                [
                    requests.Request(
                        "POST",
                        f"{origin}/images",
                        files={"proof.png": "/mnt/proof.png"},
                    )
                ],
            )
        ],
    )
    def test_identify_http_requests(self, proof, R, prefix, expected):
        ctx = invoke.context.Context()  # empty context

        results = agent.identify_http_requests(ctx, proof, R, prefix)

        assert len(results) == len(expected)

        for index, actual in enumerate(results):
            assert actual.__dict__ == expected[index].__dict__
