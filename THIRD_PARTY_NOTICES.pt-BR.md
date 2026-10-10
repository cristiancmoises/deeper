# Avisos de terceiros

[English](THIRD_PARTY_NOTICES.md) | **Português (Brasil)**

Deeper é uma interface independente que usa Maigret como dependência; não é o
projeto oficial Maigret.

- **Maigret 0.6.6**: MIT, Copyright (c) 2020–2026 Soxoj. O texto original da
  licença, extraído da distribuição instalada, está em `LICENSE-MAIGRET`.
  Fontes oficiais: [GitHub](https://github.com/soxoj/maigret) e
  [PyPI](https://pypi.org/project/maigret/0.6.6/). Agradecemos ao Soxoj por
  disponibilizar o Maigret sob a licença MIT.
- **Deeper 0.3.0**: MIT; consulte `LICENSE`.
- Flask, Waitress e demais dependências mantêm seus próprios avisos nas
  distribuições. O arquivo de lock registra as versões utilizadas; este pacote
  não redistribui os binários dessas bibliotecas.

A imagem Docker destinada exclusivamente ao Deeper remove testes de
dependências, bytecode, ferramentas de instalação e traduções do `pycountry` que
não são utilizadas. O código e a base Maigret, os dados de países, as
bibliotecas necessárias e os arquivos de licença/avisos são preservados. O
motor Maigret não recebe patches. Para usar outros recursos do CLI Maigret ou
traduções de terceiros, instale o pacote completo em um ambiente separado.

Referências da licença: [licença Maigret](https://github.com/soxoj/maigret/blob/main/LICENSE)
e `maigret-0.6.6.dist-info/licenses/LICENSE` da instalação validada.
