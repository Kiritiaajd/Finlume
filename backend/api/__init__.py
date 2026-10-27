"""Shared DRF plumbing for every API module: the error envelope and pagination.

Endpoints themselves live in each app's ``api`` package (``apps/<app>/api/``).
Business logic never lives here; it belongs in ``services``.
"""
