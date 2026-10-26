"""Cross-cutting HTTP concerns shared by all API modules.

Scope is deliberately narrow: request IDs, the API error envelope,
pagination, and the health endpoint. Domain models and business logic do not
belong in this app.
"""
