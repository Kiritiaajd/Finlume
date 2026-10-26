"""``manage.py check`` rules that keep private documents out of public paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, register


@register("security", deploy=False)
def check_private_storage_location(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    private_root = Path(settings.PRIVATE_STORAGE_ROOT).resolve()
    public_roots = [settings.STATIC_ROOT, *getattr(settings, "STATICFILES_DIRS", [])]
    if getattr(settings, "MEDIA_ROOT", ""):
        public_roots.append(settings.MEDIA_ROOT)

    errors: list[CheckMessage] = []
    for public_root in public_roots:
        if not public_root:
            continue
        public_path = Path(public_root).resolve()
        if private_root == public_path or public_path in private_root.parents:
            errors.append(
                Error(
                    f"PRIVATE_STORAGE_ROOT ({private_root}) is inside a publicly "
                    f"served directory ({public_path}).",
                    hint="Point FINLUME_PRIVATE_STORAGE_ROOT outside static and media roots.",
                    id="finlume.E001",
                )
            )
    return errors
