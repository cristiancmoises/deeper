# Deeper 0.5.0: validação

[English](../VALIDATION.md) | **Português (Brasil)**

Data: 17 de outubro de 2026. A versão acrescenta referências por nome completo
e documento público via SecuritySearch sem chave (Brave gratuito por padrão,
Google CSE gratuito opcional), preservando o modo por usuário com Maigret 0.6.6.
As verificações locais automatizadas e de navegador passaram, incluindo observações
reais limitadas do provedor e verificação do wheel instalado. A qualificação da
imagem e de produção permanece **pendente**. Não exige conta ou chave do provedor.

## Verificações locais e etapas abertas da versão

| Verificação | Evidência e escopo |
| --- | --- |
| Suíte automatizada completa | 262 testes passaram em 13,45 segundos; saída 0. Contratos controlados de provedor/aplicação/tarefas/interface não comprovam cobertura externa. |
| Verificações estáticas | Ruff, formatação e Pyright passaram nos nove arquivos Python alterados; saída 0. |
| QA no navegador | Chromium com sandbox passou nas larguras 320, 768, 1024 e 1440, com texto a 200% e limites Unicode. Dezesseis casos de formulário nativo cobriram ambos os mecanismos com e sem JavaScript. Fixtures controladas verificam comportamento, não achados do provedor. |
| Provedor real pela interface local | Três tarefas limitadas na aplicação local real: Brave com “GNU Guix” entre aspas/PDF concluiu com 10 referências; nome completo acentuado com qualquer tipo concluiu com 10 referências (conteúdos privados não publicados); Google CSE com “GNU Guix”/PDF gerou erro honesto de indisponibilidade, preservando mecanismo `google`. Não foram observados alternativa paga, troca automática de mecanismo, recarregamento após a navegação inicial ao resultado ou erros do navegador. |
| Avisos de dependências | Novo `pip-audit` verificou 68 pacotes fixados: zero vulnerabilidades conhecidas e zero pacotes ignorados; saída 0. Verificação pontual, não prova de ausência de vulnerabilidades. |
| Compose e documentação | Sintaxe e padrões renderizados passaram: agendamento 2/64/2, cache 60 segundos, retenção 900 segundos, provedor 100/dia e timeout 12 segundos, sem chave, bind privado, sistema somente leitura, capacidades removidas, limite de 128 PIDs, RAM 512 MiB / combinado 1 GiB. TOML/versão e links Markdown locais passaram. |
| Wheel substituto instalado | `deeper_maigret-0.5.0-py3-none-any.whl`, SHA-256 `b38f3ac1070511bdaa1c8309bd264684304a2a96ef123be81c71ea8298417c28`, passou na verificação fora do checkout a partir de `site-packages` instalado, com Python 3.12.12 e Maigret 0.6.6. A verificação da base encontrou 10 sites; Maigret real com fixtures HTTP locais sintéticas concluiu 3 verificações, com 1 resultado inconclusivo e 1 perfil encontrado. Health/versão, HTML/CSP, assets instalados e formulários nativos dos mecanismos gratuitos passaram. Essas fixtures locais não são achados em sites públicos. |
| Imagem da versão | Pendentes build e verificações da imagem substituta exata. A evidência do wheel instalado não qualifica o container ou a implantação. |
| Cobertura real adicional | Não estabelecida para DOCX, vazios legítimos, todos os filtros/nomes ou disponibilidade sustentada. As três tarefas acima são a evidência real da integração. |
| Qualificação em produção | Pendentes artefato/versão exatos, `/health`, nome, concorrência entre modos, memória, isolamento e ausência de OOM. O link público não certifica esta versão. |
| Capturas públicas | Interface local real 0.5.0 em Chromium com sandbox: formulário nome/PDF/Brave com consentimento desmarcado e dez referências reais Brave para “GNU Guix”/PDF. O formulário não afirma achados de documentos para o nome preenchido. O exemplo público não é pessoal; tipos são inferidos pelas URLs, sem download ou verificação de conteúdo/MIME. |

O baseline de 233 testes e as verificações de wheel instalado/navegador do
candidato Serper anterior são históricos; não qualificam os artefatos substitutos
ou a implantação. Fixtures Maigret usam o motor real com HTTP local e perfis
sintéticos. Apenas a linha de provedor real e sua captura pública representam
observações externas; resultados de fixtures não devem ser publicados como achados reais.

## Reprodução

Use o ambiente de QA existente do projeto; ferramentas de navegador e build
são externas ao desenvolvimento, sem novas dependências de runtime:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_documents.py tests/test_name_jobs.py tests/test_name_app.py tests/test_document_ui.py
docker compose config --quiet
.venv/bin/python -m build --wheel
.venv/bin/python tests/verify_ui.py --browser /caminho/do/chromium --output /tmp/deeper-username-qa
.venv/bin/python tests/verify_documents_ui.py --browser /caminho/do/chromium --output /tmp/deeper-document-qa
```

Teste o wheel em ambiente novo fora do checkout com dependências de runtime
fixadas por hashes. Confirme versão instalada, base Maigret, `/health`, HTML/CSS,
os dois scripts de progresso, ícones dos fontes e arquivos de licença. O health
verifica disponibilidade dos pacotes; não valida conectividade do SecuritySearch
ou dos mecanismos nem cobertura.

Testes reais precisam de orçamento limitado de chamadas, sem conta, chave ou API
paga. Registre mecanismo escolhido e resultados reais separados das fixtures.
O Google CSE pode limitar requisições; HTTP 503 ou proteção contra bots deve gerar
indisponibilidade honesta. Não tente mecanismo pago, troca automática de mecanismo,
reúso de cookies pessoais ou resolução de CAPTCHA. HTTP 200 também precisa do
formato JSON válido de sucesso antes de ser registrado como sucesso.

## Limites desta evidência

- Consulta com nome exato entre aspas e referência do índice não comprovam
  identidade, conteúdo, MIME, disponibilidade ou completude. Tipos desconhecidos
  permanecem não verificados; resposta vazia não comprova ausência.
- O timeout do provedor é HTTP normal do `urllib` (12 segundos por padrão,
  configurável de 1 a 30), não o watchdog do processo por usuário nem um prazo
  absoluto. Respostas têm limite de 1 MiB, sem repetição automática.
- A proteção de 100 chamadas por dia UTC e o intervalo de um segundo protegem
  recursos compartilhados por processo; o contador zera no reinício. Não são
  controles de cobrança. A integração não usa API paga nem troca automática de mecanismo.
- Os modos compartilham padrões de 2 workers/64 globais/2 por sessão, cache
  privado de 60 segundos e retenção de concluídas de 900 segundos. Execute uma
  instância HTTP. Limites por sessão controlam capacidade, não identidade de bots.
- Benchmarks anteriores em [PERFORMANCE.md](PERFORMANCE.md) são medições locais
  históricas por usuário. Não medem latência SecuritySearch, tamanho da imagem nova,
  vazão em produção ou cobertura de sites públicos.
- Suporte previsto a Python 3.11/3.12 e documentação Windows não comprovam teste
  recente em todo sistema/interpretador. Registre as execuções reais; testes de
  sinais Unix não comprovam comportamento Windows.
