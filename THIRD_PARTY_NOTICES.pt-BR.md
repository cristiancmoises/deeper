# Avisos de terceiros

[English](THIRD_PARTY_NOTICES.md) | **Português (Brasil)**

Deeper é uma interface independente que usa Maigret como dependência; não é o
projeto oficial Maigret.

- **Maigret 0.6.6**: MIT, Copyright (c) 2020–2026 Soxoj. O texto original da
  licença, extraído da distribuição instalada, está em `LICENSE-MAIGRET`.
  Fontes oficiais: [GitHub](https://github.com/soxoj/maigret) e
  [PyPI](https://pypi.org/project/maigret/0.6.6/). Agradecemos ao Soxoj por
  disponibilizar o Maigret sob a licença MIT.
- **Deeper 0.5.0**: MIT; consulte `LICENSE`.
- Flask, Waitress e demais dependências mantêm seus próprios avisos nas
  distribuições. O arquivo de lock registra as versões utilizadas; este pacote
  não redistribui os binários dessas bibliotecas.

## Logotipos dos links para o código-fonte

- **Forgejo** (`deeper/static/icons/forgejo.svg`): logotipo de
  [Caesar Schinas](https://caesarschinas.com/), licenciado sob
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  [Crédito e identidade visual originais](https://codeberg.org/forgejo/meta/src/branch/readme/branding/README.md).
  O SVG preserva este crédito e aviso de licença.
- **Codeberg** (`deeper/static/icons/codeberg.svg`):
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), conforme o
  [repositório oficial de design](https://codeberg.org/Codeberg/Design).
  Codeberg e seu logotipo são marcas de Codeberg e.V.
- Os traçados de Forgejo e Codeberg vêm do
  [Simple Icons, commit 4d29a35](https://github.com/simple-icons/simple-icons/tree/4d29a35c954699b389a834aacc97dd6e7e74143c/icons).
  A geometria foi preservada; o preenchimento branco foi aplicado para o fundo escuro.
- **GitHub** (`deeper/static/icons/github.svg`): arquivo branco
  `GitHub_Invertocat_White.svg`, sem alterações, extraído do
  [pacote oficial de logotipos](https://brand.github.com/GitHub_Logos.zip).
  Os direitos autorais e as marcas pertencem à GitHub, Inc.; o uso aponta para
  o repositório GitHub deste projeto, conforme as
  [diretrizes oficiais de uso](https://brand.github.com/foundations/logo).

A imagem Docker destinada exclusivamente ao Deeper remove testes de
dependências, bytecode, ferramentas de instalação e traduções do `pycountry` que
não são utilizadas. O código e a base Maigret, os dados de países, as
bibliotecas necessárias e os arquivos de licença/avisos são preservados. O
motor Maigret não recebe patches. Para usar outros recursos do CLI Maigret ou
traduções de terceiros, instale o pacote completo em um ambiente separado.

Referências da licença: [licença Maigret](https://github.com/soxoj/maigret/blob/main/LICENSE)
e `maigret-0.6.6.dist-info/licenses/LICENSE` da instalação validada.
