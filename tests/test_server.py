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
        "method, origin, path, multipart_field_name, accept, content_type, body, status_code",
        [
            ("OPTIONS", origin, "/images", None, "text/n3", "text/n3", None, 200),
            ("OPTIONS", origin, "/images/0", None, "text/n3", "text/n3", None, 200),
            (
                "OPTIONS",
                origin,
                "/images/0/thumbnail",
                None,
                "text/n3",
                "text/n3",
                None,
                200,
            ),
            (
                "POST",
                origin,
                "/images",
                "image",
                "image/png",
                "text/n3",
                f"{test_data_base_path}/example.png",
                201,
            ),
            (
                "POST",
                origin,
                "/images",
                "image",
                "text/n3",
                "application/problem+json",
                f"{test_data_base_path}/example.png",
                406,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a",
                None,
                "image/png",
                "image/png",
                f"{test_data_base_path}/example.png",
                200,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a/thumbnail",
                None,
                "image/png",
                "image/png",
                None,
                200,
            ),
            (
                "GET",
                origin,
                "/images/_",
                None,
                "image/png",
                "application/problem+json",
                None,
                404,
            ),
            (
                "GET",
                origin,
                "/images/_/thumbnail",
                None,
                "image/png",
                "application/problem+json",
                None,
                404,
            ),
        ],
    )
    def test_send_request(
        self,
        method,
        origin,
        path,
        multipart_field_name,
        accept,
        content_type,
        body,
        status_code,
    ):
        href = f"{origin}{path}"
        headers = {"accept": accept}
        files = None

        if body is not None:
            file_name = body.split("/")[-1]
            files = file_name
            files = {multipart_field_name: (file_name, open(body, "rb"))}

        # https://2.python-requests.org/en/master/api/#requests.request
        logger.debug(f"{method} {href}")
        r = requests.request(method, href, headers=headers, files=files)

        assert r.status_code == status_code
        assert r.headers["content-type"].split(";")[0] == content_type
