"""Throttle for adding organization members by email."""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class MemberAddThrottle(UserRateThrottle):
    """Limits how many addresses one user can try per hour.

    Adding a member by email reveals whether the address is registered, so
    this bounds account enumeration (tenancy plan §5).
    """

    scope = "organization_member_add"
