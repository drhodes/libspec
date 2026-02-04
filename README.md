# libspec

`libspec` is a library for **Specification Driven Development** in
Python. Similar in spirit to object relation mapping (ORM), libspec
offers a map to specifications, or object specification mapping
(OPM). Instead of generating SQL, we're generating specs geared
towards code generation with LLMs.

The aim on the machine side is to avoid pitfalls encountered by LLMs,
such as underspecified goals. Context overwhelm will be managed by
abstraction. The user needs good software design skills for drawing
sensible interface and library boundaries.

Axiomatically, on the human side we still need to understand how the
code is organized. The spec should encode the organization.

Your spec.py should live in a git repo and will evolve with the
project.



### Example Spec







