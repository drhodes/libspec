# libspec/store.py
from .common import Component, Implemented, Snapshot


class StoreError(Exception):
    pass


class StoreNotFoundError(StoreError):
    pass


class SpecStoreNotFoundError(StoreNotFoundError):
    pass


def get_store(*args, **kwargs):
    raise NotImplementedError(
        "SpecStore database has been removed. Use stateless Git-native workflows."
    )
