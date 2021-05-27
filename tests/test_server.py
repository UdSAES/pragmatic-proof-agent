#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Test for verifying key functions work as expected."""

import os

import pytest
import requests

class TestImageResizeAPI(object):
    origin = os.environ["IMG_API_ORIGIN"]

    @pytest.mark.parametrize("filepath, origin", [("./tests/001.png", origin)])
    def test_add_image(self, filepath, origin):
        href = f"{origin}/images"
        files = {"image": ("example.png", open(filepath, "rb"))}
        r = requests.post(href, files=files)

        print(r.headers)

        assert r.status_code == 201
