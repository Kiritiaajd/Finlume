"""Adapters between Finlume and external systems (storage, providers, jobs).

Infrastructure may depend on Django and third-party libraries. The ``domain``
package must never import from here. ``providers/`` (market data, AI) and
``jobs/`` (background processing) are introduced with their first real
consumer; see docs/architecture/DOMAIN_BOUNDARIES.md.
"""
