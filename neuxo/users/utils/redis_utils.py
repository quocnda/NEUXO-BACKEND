import os

from django.core.cache import cache
from dotenv import load_dotenv

load_dotenv()
TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "15"))
REFRESH_TOKEN_TTL_MINUTES = int(os.getenv("REFRESH_TOKEN_TTL_MINUTES", "60"))


def pushDataToRedis(key, data, ttl):
    cache.set(key, data, int(ttl))


def getDataFromRedis(key):
    data = cache.get(key)
    return data


def deleteDataFromRedis(key):
    cache.delete(key)


def addingTokenToRefresh(user, token, refresh_token):
    pushDataToRedis(
        str("ACCESS_TOKEN_" + str(user.id)), token, int(TOKEN_TTL_MINUTES * 60)
    )
    pushDataToRedis(
        str("REFRESH_TOKEN_" + str(user.id)),
        refresh_token,
        int(REFRESH_TOKEN_TTL_MINUTES * 60),
    )


def deleteTokenToRefresh(user):
    data_redis = getDataFromRedis(str("ACCESS_TOKEN_" + str(user.id)))
    if data_redis is not None:
        deleteDataFromRedis(str("ACCESS_TOKEN_" + str(user.id)))
        deleteDataFromRedis(str("REFRESH_TOKEN_" + str(user.id)))
