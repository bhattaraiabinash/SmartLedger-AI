import redis
from decouple import config

_redis_client = redis.Redis.from_url(config("CELERY_BROKER_URL"), decode_responses=True)

PRICE_CACHE_TTL_SECONDS = 300  # 5 minutes — short-lived, just for the duration of a reconciliation batch


def get_cached_vendor_price(vendor_id: str, product_id: str) -> str | None:
    key = f"price:{vendor_id}:{product_id}"
    return _redis_client.get(key)


def set_cached_vendor_price(vendor_id: str, product_id: str, price: str) -> None:
    key = f"price:{vendor_id}:{product_id}"
    _redis_client.set(key, price, ex=PRICE_CACHE_TTL_SECONDS)