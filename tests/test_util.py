#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Unit tests for utitily functions."""

import re

import pytest

import agent


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
