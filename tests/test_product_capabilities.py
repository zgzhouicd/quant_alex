# -*- coding: utf-8 -*-
from src.product_capabilities import PRODUCT_CAPABILITIES, get_product_capabilities


def test_product_capabilities_shape():
    payload = get_product_capabilities()
    assert "items" in payload
    assert payload["items"]["market_scope"] == PRODUCT_CAPABILITIES["market_scope"]
