import uuid

import pytest

from app.db.redis import redis_client
from app.security.rate_limiter import check_message_rate_limit, increment_message_count


@pytest.fixture
async def make_org_id():
    created_ids: list[str] = []

    def _factory() -> str:
        org_id = str(uuid.uuid4())
        created_ids.append(org_id)
        return org_id

    yield _factory

    for org_id in created_ids:
        keys = [key async for key in redis_client.scan_iter(match=f"msg_count:{org_id}:*")]
        if keys:
            await redis_client.delete(*keys)


async def test_under_cap_allows_messages(make_org_id):
    org_id = make_org_id()

    assert await check_message_rate_limit(org_id, max_per_hour=5) is True


async def test_cap_hit_denies_further_messages(make_org_id):
    org_id = make_org_id()

    for _ in range(5):
        await increment_message_count(org_id)

    assert await check_message_rate_limit(org_id, max_per_hour=5) is False


async def test_org_below_max_still_allowed_after_some_messages(make_org_id):
    org_id = make_org_id()

    for _ in range(3):
        await increment_message_count(org_id)

    assert await check_message_rate_limit(org_id, max_per_hour=5) is True


async def test_different_orgs_have_independent_counters(make_org_id):
    org_a = make_org_id()
    org_b = make_org_id()

    for _ in range(5):
        await increment_message_count(org_a)

    assert await check_message_rate_limit(org_a, max_per_hour=5) is False
    assert await check_message_rate_limit(org_b, max_per_hour=5) is True
