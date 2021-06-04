#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Test for verifying key functions work as expected."""

import os

import pytest
import requests
from loguru import logger


test_data_base_path = os.path.normpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "data")
)


class TestImageResizeAPI(object):
    origin = os.environ["IMG_API_ORIGIN"]

    @pytest.mark.parametrize(
        "method, origin, path, accept, body, status_code",
        [
            ("OPTIONS", origin, "/images", "text/n3", None, 200),
            ("OPTIONS", origin, "/images/0", "text/n3", None, 200),
            ("OPTIONS", origin, "/images/0/thumbnail", "text/n3", None, 200),
            (
                "POST",
                origin,
                "/images",
                "image/png",
                f"{test_data_base_path}/example.png",
                201,
            ),
            (
                "POST",
                origin,
                "/images",
                "text/n3",
                f"{test_data_base_path}/example.png",
                406,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a",
                "image/png",
                f"{test_data_base_path}/example.png",
                200,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a/thumbnail",
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
        files = None

        if status_code >= 400:
            expected_content_type = "application/problem+json"
        else:
            expected_content_type = accept

        if body is not None:
            file_name = body.split("/")[-1]
            files = {"image": (file_name, open(body, "rb"))}

        # https://2.python-requests.org/en/master/api/#requests.request
        logger.debug(f"{method} {href}")
        r = requests.request(method, href, headers=headers, files=files)

        assert r.status_code == status_code
        assert r.headers["content-type"].split(";")[0] == expected_content_type
