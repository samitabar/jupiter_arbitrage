import typing as t

import redis
import json


__all__ = [
    'Tabar',
    'CacherException',
    'EmptyCacheException',
]


class CacherException(Exception):
    pass


class EmptyCacheException(CacherException):
    pass


class BaseRedis:
    def __init__(self, host: str, port: int, db: int, password: str = None) -> None:
        self.__redis_conn = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)

    def _base_cache_data(self, key: str, data: str, expire: int = None) -> None:
        self.__redis_conn.set(key, data, ex=expire)

    def _base_read_data(self, key: str) -> t.Union[str, None]:
        data = self.__redis_conn.get(key)

        if data is None:
            return None
        else:
            return data

    def _read_all(self) -> t.List:
        return self.__redis_conn.keys()


class Tabar(BaseRedis):
    def __init__(self, host: str, port: int, db: int, password: str = None):
        super().__init__(host, port, db, password)

    def cache_price(self, symbol: str, data: t.Dict, expire_time: t.Optional[int] = None) -> None:
        _data = json.dumps(data)
        self._base_cache_data(symbol.upper(), _data, expire_time)

    def read_price(self, symbol: str) -> t.Dict:
        data = self._base_read_data(symbol.upper())

        if data is None:
            raise EmptyCacheException(f'No cache found for -> {symbol}')

        return json.loads(data)
