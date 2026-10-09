# Third-party notices

**English** | [Português (Brasil)](THIRD_PARTY_NOTICES.pt-BR.md)

Deeper is an independent interface that uses Maigret as a dependency; it is not
the official Maigret project.

- **Maigret 0.6.6**: MIT, Copyright (c) 2020–2026 Soxoj. The original license
  text from the installed distribution is in `LICENSE-MAIGRET`. Official
  sources: [GitHub](https://github.com/soxoj/maigret) and
  [PyPI](https://pypi.org/project/maigret/0.6.6/). Thank you to Soxoj for making
  Maigret available under the MIT license.
- **Deeper 0.2.0**: MIT; see `LICENSE`.
- Flask, Waitress, and other dependencies retain their own notices in their
  distributions. The lock file records the versions used; this package does not
  redistribute those libraries' binaries.

The Docker image intended only for Deeper removes dependency tests, bytecode,
installation tools, and unused `pycountry` translations. Maigret code and its
database, country data, required libraries, and license/notice files are
preserved. The Maigret engine is not patched. For other Maigret CLI features or
third-party translations, install the full package in a separate environment.

License references: [Maigret license](https://github.com/soxoj/maigret/blob/main/LICENSE)
and `maigret-0.6.6.dist-info/licenses/LICENSE` from the validated installation.
