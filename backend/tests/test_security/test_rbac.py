import uuid

from app.models.enums import UserRole
from app.models.user import User
from app.security.rbac import check_org_access


def _make_user(role: UserRole, org_id: uuid.UUID | None) -> User:
    return User(id=uuid.uuid4(), email="user@example.com", role=role, org_id=org_id)


def test_super_admin_always_has_access():
    user = _make_user(UserRole.super_admin, org_id=None)

    assert check_org_access(user, uuid.uuid4()) is True


def test_org_staff_has_access_to_own_org():
    org_id = uuid.uuid4()
    user = _make_user(UserRole.org_staff, org_id=org_id)

    assert check_org_access(user, org_id) is True


def test_org_staff_denied_access_to_other_org():
    user = _make_user(UserRole.org_staff, org_id=uuid.uuid4())

    assert check_org_access(user, uuid.uuid4()) is False
