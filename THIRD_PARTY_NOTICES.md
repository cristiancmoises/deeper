# Third-party notices

**English** | [Português (Brasil)](THIRD_PARTY_NOTICES.pt-BR.md)

Deeper is an independent interface that uses Maigret as a dependency; it is not
the official Maigret project.

- **Maigret 0.6.6**: MIT, Copyright (c) 2020–2026 Soxoj. The original license
  text from the installed distribution is in `LICENSE-MAIGRET`. Official
  sources: [GitHub](https://github.com/soxoj/maigret) and
  [PyPI](https://pypi.org/project/maigret/0.6.6/). Thank you to Soxoj for making
  Maigret available under the MIT license.
- **Deeper 0.3.0**: MIT; see `LICENSE`.
- Flask, Waitress, and other dependencies retain their own notices in their
  distributions. The lock file records the versions used; this package does not
  redistribute those libraries' binaries.

## Source-link logos

- **Forgejo** (`deeper/static/icons/forgejo.svg`): logo by
  [Caesar Schinas](https://caesarschinas.com/), licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  [Upstream attribution and branding](https://codeberg.org/forgejo/meta/src/branch/readme/branding/README.md).
  The SVG retains this credit and license notice.
- **Codeberg** (`deeper/static/icons/codeberg.svg`):
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), per the
  [official design repository](https://codeberg.org/Codeberg/Design).
  Codeberg and its logo are trademarks of Codeberg e.V.
- The Forgejo and Codeberg paths come from
  [Simple Icons, commit 4d29a35](https://github.com/simple-icons/simple-icons/tree/4d29a35c954699b389a834aacc97dd6e7e74143c/icons).
  Their geometry is unchanged; white fill was applied for the dark background.
- **GitHub** (`deeper/static/icons/github.svg`): the unmodified white
  `GitHub_Invertocat_White.svg` from the
  [official logo archive](https://brand.github.com/GitHub_Logos.zip).
  Copyright and trademarks belong to GitHub, Inc.; used to link to this
  project's GitHub repository under the
  [official logo usage guidelines](https://brand.github.com/foundations/logo).

The Docker image intended only for Deeper removes dependency tests, bytecode,
installation tools, and unused `pycountry` translations. Maigret code and its
database, country data, required libraries, and license/notice files are
preserved. The Maigret engine is not patched. For other Maigret CLI features or
third-party translations, install the full package in a separate environment.

License references: [Maigret license](https://github.com/soxoj/maigret/blob/main/LICENSE)
and `maigret-0.6.6.dist-info/licenses/LICENSE` from the validated installation.
