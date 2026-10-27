"""Authorization: the single resolver every tenant endpoint and job uses."""

from .resolvers import require_organization_role, require_workspace_role

__all__ = ["require_organization_role", "require_workspace_role"]
