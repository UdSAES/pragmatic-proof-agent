#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Test for verifying key functions work as expected."""

import os

import pytest
import requests

class TestImageResizeAPI(object):
    origin = os.environ["IMG_API_ORIGIN"]

    @pytest.mark.parametrize("filepath, origin", [("./tests/example.png", origin)])
    def test_add_image(self, filepath, origin):
        href = f"{origin}/images"
        file_name = filepath.split('/')[-1]
        files = {"image": (file_name, open(filepath, "rb"))}
        r = requests.post(href, files=files)

        print(r.headers)

        assert r.status_code == 201

    @pytest.mark.parametrize("image_id, origin", [("0c2d99c897ad212c3fd8823e9b0b06ec", origin)])
    def test_get_image(self, image_id, origin):
        href = f"{origin}/images/{image_id}"
        r = requests.get(href)

        assert r.status_code == 200

    @pytest.mark.parametrize("image_id, origin", [("0c2d99c897ad212c3fd8823e9b0b06ec", origin)])
    def test_get_thumbnail(self, image_id, origin):
        href = f"{origin}/images/{image_id}/thumbnail"
        r = requests.get(href)

        assert r.status_code == 200

class TestRESTdescDiscovery(object):
    origin = os.environ["IMG_API_ORIGIN"]

    @pytest.mark.parametrize("origin,path", [
        (origin, "/images"),
        (origin, "/images/1"),
        (origin, "/images/1/thumbnail"),
    ])
    def test_get_rest_desc(self, origin, path):
        href = f"{origin}{path}"
        r = requests.options(href)

        assert r.status_code == 200
