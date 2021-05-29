#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Test for verifying key functions work as expected."""

import os

import pytest
import requests
from loguru import logger


class TestImageResizeAPI(object):
    origin = os.environ["IMG_API_ORIGIN"]

    @pytest.mark.parametrize(
        "method, origin, path, accept, body, status_code",
        [
            ("OPTIONS", origin, "/images", "text/n3", None, 200),
            ("OPTIONS", origin, "/images/0/thumbnail", "text/n3", None, 200),
            ("POST", origin, "/images", "image/png", "./tests/example.png", 201),
            ("POST", origin, "/images", "text/n3", "./tests/example.png", 406),
            (
                "GET",
                origin,
                "/images/0c2d99c897ad212c3fd8823e9b0b06ec",
                "image/png",
                "./tests/example.png",
                200,
            ),
            (
                "GET",
                origin,
                "/images/0c2d99c897ad212c3fd8823e9b0b06ec/thumbnail",
                "image/png",
                None,
                200,
            ),
            ("GET", origin, "/images/_", "image/png", None, 404),
            (
                "GET",
                origin,
                "/images/_/thumbnail",
                "image/png",
                None,
                404,
            ),
        ],
    )
    def test_send_request(self, method, origin, path, accept, body, status_code):
        href = f"{origin}{path}"
        headers = {"accept": accept}

        if status_code >= 400:
            expected_content_type = "application/problem+json"
        else:
            expected_content_type = accept

        if body is not None:
            file_name = body.split("/")[-1]
            files = {"image": (file_name, open(body, "rb"))}

        if method == "POST":
            logger.debug(f"{method} {href}")
            r = requests.post(href, headers=headers, files=files)

        if method == "GET":
            logger.debug(f"{method} {href}")
            r = requests.get(href, headers=headers)

        if method == "OPTIONS":
            logger.debug(f"{method} {href}")
            r = requests.options(href, headers=headers)

        assert r.status_code == status_code
        assert r.headers["content-type"].split(";")[0] == expected_content_type
