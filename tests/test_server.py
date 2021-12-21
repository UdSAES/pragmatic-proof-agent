#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Test for verifying key functions work as expected."""

import os
from http import HTTPStatus

import pytest
import requests
from loguru import logger

test_data_base_path = os.path.normpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "data")
)


class TestImageResizeAPI(object):
    origin = os.getenv("API_ORIGIN", "")

    @pytest.mark.parametrize(
        "method, origin, path, accept, content_type, body, status_code",
        [
            (
                "OPTIONS",
                origin,
                "/images",
                "text/n3",
                "text/n3",
                None,
                HTTPStatus.OK,
            ),
            (
                "OPTIONS",
                origin,
                "/images/0/thumbnail",
                "text/n3",
                "text/n3",
                None,
                HTTPStatus.OK,
            ),
            (
                "POST",
                origin,
                "/images",
                "text/n3",
                "text/n3",
                f"{test_data_base_path}/example.png",
                HTTPStatus.CREATED,
            ),
            (
                "POST",
                origin,
                "/images",
                "application/ld+json",
                "application/ld+json",
                f"{test_data_base_path}/example.png",
                HTTPStatus.CREATED,
            ),
            (
                "POST",
                origin,
                "/images",
                "text/html",
                "application/problem+json",
                f"{test_data_base_path}/example.png",
                HTTPStatus.NOT_ACCEPTABLE,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a",
                "image/png",
                "image/png",
                f"{test_data_base_path}/example.png",
                HTTPStatus.OK,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a/thumbnail",
                "image/png",
                "image/png",
                None,
                HTTPStatus.OK,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a/thumbnail",
                "text/n3",
                "text/n3",
                None,
                HTTPStatus.OK,
            ),
            (
                "GET",
                origin,
                "/images/90007eb1c2af27c8fbac3fc6db2f801a/thumbnail",
                "application/ld+json",
                "application/ld+json",
                None,
                HTTPStatus.OK,
            ),
            (
                "GET",
                origin,
                "/images/_",
                "image/png",
                "application/problem+json",
                None,
                HTTPStatus.NOT_FOUND,
            ),
            (
                "GET",
                origin,
                "/images/_/thumbnail",
                "image/png",
                "application/problem+json",
                None,
                HTTPStatus.NOT_FOUND,
            ),
        ],
    )
    def test_send_request(
        self,
        method,
        origin,
        path,
        accept,
        content_type,
        body,
        status_code,
    ):
        href = f"{origin}{path}"
        headers = {"accept": accept}
        data = None

        if body is not None:
            with open(body, "rb") as fp:
                data = fp.read()
            
            headers["content-type"] = "application/octet-stream"

        # https://2.python-requests.org/en/master/api/#requests.request
        logger.debug(f"{method} {href}")
        r = requests.request(method, href, headers=headers, data=data)

        assert r.status_code == status_code
        assert r.headers["content-type"].split(";")[0] == content_type
