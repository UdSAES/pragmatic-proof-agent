#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Unit tests for utitily functions."""

import re
import pytest


def correct_n3_syntax(input):
    """Fix N3 syntax variants not universally supported."""

    # FIXME this should be imported from `agent.py` instead of copy-pasted!!

    pattern = re.compile(
        r"^(?P<prefix>PREFIX) (?P<abbrv>[\w-]+:) (?P<url><[\w:\/\.#]+>)$", re.MULTILINE
    )

    output = pattern.sub(r"@prefix \g<abbrv> \g<url>.", input)
    return output


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
        actual = correct_n3_syntax(input)

        assert actual == expected
