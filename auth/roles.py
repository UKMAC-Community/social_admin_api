from enum import Enum
from typing import FrozenSet, Iterable, Set


class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    CONTENT_MANAGER = "content_manager"
    STAFF_MANAGER = "staff_manager"
    LEGACY_MANAGER = "manager"


CONTENT_DASHBOARD_ROLES: FrozenSet[UserRole] = frozenset(
    {
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
        UserRole.CONTENT_MANAGER,
        UserRole.LEGACY_MANAGER,
    }
)
STAFF_DASHBOARD_ROLES: FrozenSet[UserRole] = frozenset(
    {
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
        UserRole.STAFF_MANAGER,
    }
)
USER_MANAGEMENT_ROLES: FrozenSet[UserRole] = frozenset(
    {
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
    }
)
DASHBOARD_ROLES: FrozenSet[UserRole] = frozenset(
    {
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
        UserRole.CONTENT_MANAGER,
        UserRole.STAFF_MANAGER,
        UserRole.LEGACY_MANAGER,
    }
)


def role_values(roles: Iterable[UserRole]) -> Set[str]:
    return {role.value for role in roles}
