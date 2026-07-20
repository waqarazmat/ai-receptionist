from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import User


async def set_tenant_context(session: AsyncSession, user: User) -> None:
    """Set the Postgres session variable RLS policies filter on.

    org_staff: app.tenant_id is set to their org, so every tenant-scoped
    table's `tenant_isolation` policy restricts rows to that org.

    super_admin: left untouched. The app connects as the tables' owner, and
    Postgres exempts owners from RLS unless FORCE ROW LEVEL SECURITY is set
    (it isn't) — so super_admin queries already see every row.
    """
    if user.role == UserRole.org_staff:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
            {"tenant_id": str(user.org_id)},
        )
