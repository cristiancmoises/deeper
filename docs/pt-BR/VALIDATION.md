# Deeper 0.5.0: validação

[English](../VALIDATION.md) | **Português (Brasil)**

Data: 17 de outubro de 2026. A versão acrescenta referências por nome completo
e documento público via SecuritySearch sem chave (Brave gratuito por padrão,
Google CSE gratuito opcional), preservando o modo por usuário com Maigret 0.6.6.
As verificações locais automatizadas e de navegador passaram, incluindo observações
reais limitadas do provedor e verificação do wheel instalado. A qualificação da
imagem e as verificações limitadas de navegador, segurança e memória em produção
também passaram no escopo abaixo. Não foram estabelecidas concorrência real ou
capacidade sustentada. Não exige conta ou chave do provedor.

## Verificações e observações em produção

| Verificação | Evidência e escopo |
| --- | --- |
| Suíte automatizada completa | Árvore integrada: 262 testes passaram em 14,12 segundos; saída 0. Contratos controlados de provedor/aplicação/tarefas/interface não comprovam cobertura externa. |
| Verificações estáticas | Ruff, formatação e Pyright passaram nos nove arquivos Python alterados; saída 0. |
| QA no navegador | Chromium com sandbox passou nas larguras 320, 768, 1024 e 1440, com texto a 200% e limites Unicode. Dezesseis casos de formulário nativo cobriram ambos os mecanismos com e sem JavaScript. Fixtures controladas verificam comportamento, não achados do provedor. |
| Provedor real pela interface local | Três tarefas limitadas na aplicação local real: Brave com “GNU Guix” entre aspas/PDF concluiu com 10 referências; nome completo acentuado com qualquer tipo concluiu com 10 referências (conteúdos privados não publicados); Google CSE com “GNU Guix”/PDF gerou erro honesto de indisponibilidade, preservando mecanismo `google`. Não foram observados alternativa paga, troca automática de mecanismo, recarregamento após a navegação inicial ao resultado ou erros do navegador. |
| Avisos de dependências | Novo `pip-audit` verificou 68 pacotes fixados: zero vulnerabilidades conhecidas e zero pacotes ignorados; saída 0. Verificação pontual, não prova de ausência de vulnerabilidades. |
| Compose e documentação | Sintaxe e padrões renderizados passaram: agendamento 2/64/2, cache 60 segundos, retenção 900 segundos, provedor 100/dia e timeout 12 segundos, sem chave, bind privado, sistema somente leitura, capacidades removidas, limite de 128 PIDs, RAM 512 MiB / combinado 1 GiB. TOML/versão e links Markdown locais passaram. |
| Wheel substituto instalado | `deeper_maigret-0.5.0-py3-none-any.whl`, SHA-256 `b38f3ac1070511bdaa1c8309bd264684304a2a96ef123be81c71ea8298417c28`, passou na verificação fora do checkout a partir de `site-packages` instalado, com Python 3.12.12 e Maigret 0.6.6. A verificação da base encontrou 10 sites; Maigret real com fixtures HTTP locais sintéticas concluiu 3 verificações, com 1 resultado inconclusivo e 1 perfil encontrado. Health/versão, HTML/CSP, assets instalados e formulários nativos dos mecanismos gratuitos passaram. Essas fixtures locais não são achados em sites públicos. |
| Imagem da versão | Construída no host do backend com Docker 26.1.5, limite de build de 512 MiB de RAM / 768 MiB combinado e 1 CPU. Commit-fonte `af52f8623c2be4deb7f62bc187deff9b8eb3c5cf`; ID `sha256:30a44f72adfdaaa51c11fa0d7239558a2241dbaeccd071caed4c75911b49fd35`; tamanho 255.663.719 bytes. A verificação dentro da imagem real passou com Python 3.12.15, Maigret 0.6.6 e site-packages instalado em `/opt/venv`: Maigret sintético local com 3 verificações / 1 inconclusivo / 1 perfil, CSP, formulários, assets, container saudável e `OOMKilled=false`. Limites de build são distintos do orçamento de runtime, que permanece igual. |
| Cobertura real adicional | Sucesso e indisponibilidade DOCX em produção estão registrados abaixo. Vazios legítimos, todos os filtros/nomes e disponibilidade sustentada não foram estabelecidos. Os resultados do provedor são intermitentes; falha não é busca vazia bem-sucedida. |
| Ativação e health em produção | A imagem acima foi ativada no bind privado existente do backend, preservando a entrada pela IONOS e a rota compartilhada dos proxies reversos. O `/health` HTTPS público retornou versão 0.5.0 e status `ok`. Health isolado não qualifica comportamento do provedor ou capacidade em produção. |
| Provedor e usuário em produção | Chromium 153 com sandbox enviou exatamente quatro tarefas por nome e uma por usuário, sem repetições: “GNU Guix” entre aspas/PDF Brave concluiu com 10 referências; usuário `gnu-guix` concluiu 500/500 verificações com seis perfis; “GNU Guix”/DOCX Brave retornou indisponibilidade com zero referências (erro, não sucesso vazio); “GNU Guix”/PDF Google CSE concluiu com 10 referências; uma tarefa separada, selecionada explicitamente no Google CSE para “Creative Commons”/DOCX, concluiu com quatro referências. Os rótulos reais foram preservados, sem alternativa paga ou troca automática. Não foram observados recarregamentos após a navegação inicial ao resultado, erros do navegador ou requisições externas do navegador. São contagens do índice/perfis, não verificação de identidade ou conteúdo de documentos. |
| Segurança e sessões em produção | Passaram as verificações HTTPS de CSP, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` e flags Secure/HttpOnly/SameSite=Strict do cookie de sessão. Outra sessão recebeu HTTP 404 da API privada de atualizações. Valores de cookies não são publicados. |
| Escopo dos dois modos | A mesma sessão aceitou ambos os modos, mas a tarefa por nome já havia concluído quando a tarefa por usuário foi enviada. Não foram observados sobreposição real, estado em fila ou benchmark de capacidade sustentada. Testes automatizados cobrem contratos de agendamento e isolamento; esta execução real não estabelece capacidade concorrente. |
| Memória e health em produção | 38 amostras entre 19:06:48 e 19:10:16 UTC de 17 de outubro registraram pico de 143,3 MiB dentro do limite de runtime de 512 MiB; todas estavam saudáveis, sem OOM e com zero reinícios. A verificação final em idle às 19:11:36 UTC registrou 50,7 MiB, saudável, zero reinícios e sem OOM. É observação limitada, não benchmark de carga ou longa duração. |
| Pré-verificação de transporte e escopo da implantação | O primeiro health com prazo de 10 segundos expirou antes de qualquer tarefa; a pré-verificação com tolerância de 30 segundos funcionou sem alterar TLS ou sandbox. Nenhum defeito do produto foi comprovado. Apenas o backend do Deeper mudou; os proxies compartilhados permaneceram iguais. O container temporário de teste e o container/imagem aposentados da 0.4 foram removidos por identidade explícita; a imagem 0.5 foi preservada e apenas seu container permanece em execução. A fonte da imagem é o commit acima; edições posteriores da versão são apenas documentais, sem alteração de runtime ou README. Nenhuma nova tarefa real foi enviada após esgotar o orçamento de chamadas. |
| Capturas públicas | Interface local real 0.5.0 em Chromium com sandbox: formulário nome/PDF/Brave com consentimento desmarcado e dez referências reais Brave para “GNU Guix”/PDF. O formulário não afirma achados de documentos para o nome preenchido. O exemplo público não é pessoal; tipos são inferidos pelas URLs, sem download ou verificação de conteúdo/MIME. |

O baseline de 233 testes e as verificações de wheel instalado/navegador do
candidato Serper anterior são históricos; não qualificam os artefatos substitutos
ou a implantação. Fixtures Maigret usam o motor real com HTTP local e perfis
sintéticos. As linhas de provedor real e a captura pública representam
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
