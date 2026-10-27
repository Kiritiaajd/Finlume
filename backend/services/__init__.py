"""Business workflows: the layer between the API (``apps``) and the ``domain``.

Each sub-package is one business capability, made of plain, typed
functions. A workflow authorizes the caller, works with the ORM inside a
transaction, calls the pure ``domain`` engine or a provider adapter, and
records audit events.

Capabilities (docs/architecture/DOMAIN_BOUNDARIES.md, section 3.3):

- Tenancy, now: ``access``, ``accounts``, ``organizations``, ``workspaces``.
- Financial, added with their first feature: ``statement_analysis``,
  ``documents``, ``stock_research``, ``portfolio_analysis``.

Rules:

- No ``rest_framework`` imports, ``Request`` objects or serializers.
- Never re-implement domain logic such as ratio formulas; call ``domain``.
- A financial capability does not import another financial capability.
  Shared needs go through ``access`` or move down into ``domain``.
- Raise ``Http404``, ``PermissionDenied`` or ``services.errors.ConflictError``.
- Use the ORM directly; there is no repository layer.
- A workflow that writes more than once is atomic on its own.
"""
