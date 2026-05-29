'''
Re-exports all concrete SpecStore backend implementations.
'''

from libspec.stores.json_lines import JsonLinesSpecStore

__all__ = [
    "JsonLinesSpecStore",
]

