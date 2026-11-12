# -*- coding: utf-8 -*-
"""HTTP middleware package."""

from api.middlewares.error_handler import add_error_handlers

__all__ = ["add_error_handlers"]
