# Python API Reference

This page contains the programmatic Python API reference for building specifications. Documentation for these interfaces is extracted dynamically from the source code.

---

## Specification Primitives

The core primitives are used to define context boundaries, requirements, and features within spec modules.

::: libspec.spec.Ctx
    options:
      show_source: true

::: libspec.spec_types.Requirement
    options:
      show_source: true

::: libspec.spec_types.Feature
    options:
      show_source: true

::: libspec.spec.Spec
    options:
      show_source: true

---

## Specification Representation

These models represent compiled specifications within snapshots.

::: libspec.store.Component
    options:
      show_source: true

---

## SpecStore Backends

The transaction storage backend interfaces are used to read and write to the transaction logs.

::: libspec.store.SpecStore
    options:
      show_source: true
      members:
        - get_snapshot
        - current_snapshot
        - list_snapshots
        - store_snapshot
        - delete_snapshot
        - restore_snapshot
        - store_dependency
        - list_dependencies
        - compact
