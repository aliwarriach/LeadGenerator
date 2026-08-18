"""The application's permission vocabulary and the roles that grant it.

Deliberately framework-free (no FastAPI, no config, no DB imports) so it can be
imported from anywhere — including `app.core.config` — without an import cycle.
The FastAPI wiring lives in `app.core.authz`.
"""

from enum import StrEnum


class Permission(StrEnum):
    """One capability. Granted to a role, required by a route.

    Named `<resource>:<action>` so a permission reads the same in code, in a
    403 body, and in the agent tool registry that will consume these later.
    """

    DASHBOARD_READ = "dashboard:read"

    LEADS_READ = "leads:read"
    LEADS_WRITE = "leads:write"
    LEADS_DELETE = "leads:delete"

    # Separate from LEADS_WRITE: moving a lead through the sales pipeline is a
    # sales action that also writes the activity log, whereas LEADS_WRITE is
    # ordinary record editing. A role can reasonably hold one without the other.
    PIPELINE_WRITE = "pipeline:write"

    ACTIVITIES_READ = "activities:read"
    ACTIVITIES_WRITE = "activities:write"

    # The three below all spend external quota (Groq / PageSpeed), so they are
    # their own permissions rather than folding into a generic write.
    AUDIT_RUN = "audit:run"
    OUTREACH_GENERATE = "outreach:generate"

    DRAFTS_READ = "drafts:read"
    DRAFTS_WRITE = "drafts:write"
    DRAFTS_DELETE = "drafts:delete"

    DISCOVERY_READ = "discovery:read"
    DISCOVERY_START = "discovery:start"
    DISCOVERY_STOP = "discovery:stop"

    # Reserved for the AI assistant (see AI_ASSISTANT_ROADMAP.md). Nothing
    # requires it yet; it exists now so roles don't need redefining later.
    ASSISTANT_USE = "assistant:use"


class Role(StrEnum):
    OWNER = "owner"
    OPERATOR = "operator"
    VIEWER = "viewer"


_READ_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.LEADS_READ,
        Permission.ACTIVITIES_READ,
        Permission.DRAFTS_READ,
        Permission.DISCOVERY_READ,
    }
)

# operator = everything an owner can do minus the two irreversible deletes.
# Kept as an explicit subtraction rather than a hand-listed set so a new
# permission is granted to operators by default and only has to be excluded
# here if it's genuinely owner-only.
_OWNER_ONLY: frozenset[Permission] = frozenset({Permission.LEADS_DELETE, Permission.DRAFTS_DELETE})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.OPERATOR: frozenset(Permission) - _OWNER_ONLY,
    Role.VIEWER: _READ_PERMISSIONS | {Permission.ASSISTANT_USE},
}


def permissions_for(role: Role) -> frozenset[Permission]:
    """Permissions granted by `role`. Unknown roles grant nothing.

    Fails closed on purpose: a role added to the enum but forgotten here
    should lock its holders out, not silently inherit someone else's access.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())
