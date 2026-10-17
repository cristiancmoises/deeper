# Deeper 0.5.0: validação

[English](../VALIDATION.md) | **Português (Brasil)**

Data: 17 de outubro de 2026. A versão acrescenta referências por nome completo
e documento público via Serper, mantendo o modo por usuário com Maigret 0.6.6.
Fixtures automatizadas do provedor e testes no navegador são separados da
evidência real. A qualificação real do Serper, da 0.5.0 em produção e das novas
capturas permanece **pendente** até configurar a chave do provedor escolhido.

## Qualificação local verificada

| Verificação | Evidência e escopo |
| --- | --- |
| Suíte automatizada completa | 233 testes passaram em 12,68 segundos; saída 0. |
| Integração de provedor e aplicação/tarefas | A suíte completa inclui payloads HTTP/provedor controlados, validação de consulta, limites de resposta, filtros, cotas/erros, exclusão da credencial, consentimento, propriedade, agendamento compartilhado e snapshots. Não são buscas reais do Serper. |
| Wheel 0.5.0 instalado | Wheel construído e instalado em ambiente virtual privado; verificador executado fora do checkout confirmou importação do `site-packages/deeper` instalado, versão 0.5.0 do pacote/health, HTML/CSS, os dois scripts de progresso, os três ícones SVG dos fontes e filtro/consentimento obrigatório no modo por nome; saída 0. |
| Maigret real com HTTP local | O smoke do wheel instalado concluiu três verificações, com um resultado inconclusivo e um perfil sintético encontrado. Apenas fixtures em loopback foram consultadas. |
| QA no navegador | QA legado por usuário e novo por documento passaram em Chromium real; saída 0. Os testes de documentos cobriram larguras 320, 768, 1024 e 1440 com resultados controlados. Nove verificações de limites Unicode também passaram. Fixtures de navegador não comprovam cobertura real do provedor. |
| Avisos de dependências | `pip-audit` das dependências fixadas com hashes verificou 68 pacotes: zero vulnerabilidades conhecidas e zero pacotes ignorados; saída 0. É uma consulta pontual de avisos, não prova de ausência de vulnerabilidades. |
| Configuração Compose | Validação de configuração e valores renderizados passou: limites compartilhados 2/64/2, cache de 60 segundos, retenção de 900 segundos, chave vazia no exemplo, padrões do provedor, 512 MiB de RAM / 1 GiB combinado e confinamento existente; saída 0. Qualificação da imagem/implantação em produção permanece pendente. |
| Smoke do provedor real | Pendente: buscas reais limitadas por nome, incluindo PDF, DOCX, nomes não ASCII, vazios legítimos, erros e comportamento dos filtros. |
| Qualificação em produção | Pendente: artefato/versão exatos, `/health`, busca por nome, concorrência entre modos, memória, isolamento de sessões e ausência de OOM na implantação Deeper. |
| Capturas públicas | As imagens atuais dos READMEs são da busca por usuário na 0.4.0. As capturas reais 0.5.0 por nome/documento ainda não as substituíram. |

As verificações locais acima passaram; as etapas de provedor real e produção
permanecem pendentes. Testes Maigret usam o motor real com
HTTP local e perfis sintéticos. Testes Serper usam respostas controladas, não
créditos ou contas reais. Fixtures no navegador verificam a interface; seus
resultados não devem ser publicados como achados reais do provedor.

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
verifica disponibilidade dos pacotes; não valida credenciais, créditos,
conectividade ou cobertura do Serper.

Testes reais exigem `SERPER_API_KEY` configurada de forma privada e orçamento
limitado de chamadas. Nunca imprima a credencial nem a inclua em relatórios,
capturas, argumentos de comandos ou Git. Chave ausente deve produzir estado
indisponível, nunca referências inventadas. Registre os resultados reais
separados das fixtures antes de declarar sucesso com o provedor.

## Limites desta evidência

- Consulta com nome exato entre aspas e referência do índice não comprovam
  identidade, conteúdo, MIME, disponibilidade ou completude. Tipos desconhecidos
  permanecem não verificados; resposta vazia não comprova ausência.
- O timeout do provedor é HTTP normal do `urllib` (12 segundos por padrão,
  configurável de 1 a 30), não o watchdog do processo por usuário nem um prazo
  absoluto. Respostas têm limite de 1 MiB, sem repetição automática.
- A proteção de 100 chamadas por dia UTC é por processo e zera no reinício. Não
  garante a cobrança de toda a conta nem controla outros clientes. Não há compra
  de créditos ou recarga automática.
- Os modos compartilham padrões de 2 workers/64 globais/2 por sessão, cache
  privado de 60 segundos e retenção de concluídas de 900 segundos. Execute uma
  instância HTTP. Limites por sessão controlam capacidade, não identidade de bots.
- Benchmarks anteriores em [PERFORMANCE.md](PERFORMANCE.md) são medições locais
  históricas por usuário. Não medem latência Serper, tamanho da imagem nova,
  vazão em produção ou cobertura de sites públicos.
- Suporte previsto a Python 3.11/3.12 e documentação Windows não comprovam teste
  recente em todo sistema/interpretador. Registre as execuções reais; testes de
  sinais Unix não comprovam comportamento Windows.
