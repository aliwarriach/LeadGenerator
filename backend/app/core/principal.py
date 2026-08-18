"""Who is making a request, and what they're allowed to do.

Framework-free like `app.core.permissions` — `app.core.config` imports
`AuthAccount` from here, so this module must not import config back.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import Permission, Role, permissions_for


class AuthAccount(BaseModel):
    """One configured HTTP Basic credential and the role it carries.

    Roles are attached to credentials rather than stored in a `users` table:
    this is a single-operator internal tool, and a table would bring password
    hashing, rotation, and an admin UI along with it for no current benefit.
    `app.core.authz.get_principal` is the single seam to change if that stops
    being true — nothing else in the app knows where a principal came from.
    """

    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    role: Role = Role.OWNER


class Principal(BaseModel):
    """The authenticated caller, resolved once per request.

    `permissions` is materialized at construction rather than derived from
    `role` on every check — a request can make dozens of checks, and this also
    leaves room for a per-account override later without touching call sites.
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    role: Role
    permissions: frozenset[Permission]

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    @classmethod
    def for_role(cls, subject: str, role: Role) -> "Principal":
        return cls(subject=subject, role=role, permissions=permissions_for(role))


class PermissionDeniedError(Exception):
    """Raised by non-HTTP layers (services, and later the agent tool layer)
    when a principal lacks a permission. Routes use `app.core.authz.require`,
    which raises `ApiError` directly instead."""

    def __init__(self, permission: Permission) -> None:
        self.permission = permission
        super().__init__(f"Permission {permission.value!r} is required")
