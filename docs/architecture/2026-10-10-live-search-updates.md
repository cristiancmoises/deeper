# Live search updates — design

**Status:** design approved; specification awaiting review  
**Date:** 10 October 2026  
**Languages:** English (default) and Português (Brasil)

## English

### Goal

Let a person follow a Deeper search without reloading the entire page every three
seconds. Show newly discovered profiles as they become available and keep the
site-check progress visible. Improve the cost of progress delivery without
claiming to make remote social sites respond faster.

### Current behavior

Maigret progress is already collected by the worker and stored in the private
in-memory job manager. The results page uses a three-second HTML meta refresh,
so each update reconstructs and transfers the whole page and all profiles.
Progress updates also carry the accumulated profile list, even when only a small
amount of new information is available.

### Proposed design

Keep the existing POST-and-redirect search flow. Replace the automatic HTML
refresh with progressive enhancement using one self-hosted JavaScript file and
a same-origin JSON updates endpoint. The results page remains server-rendered
and includes a manual refresh fallback when JavaScript is unavailable.

The endpoint accepts a nonnegative, bounded integer cursor and returns current
counters, job state, and only newly discovered profiles since that cursor. A
monotonic sequence identifies each profile event; its bounded lifetime matches
the job's existing retention, and the total possible events cannot exceed the
number of sites checked. The browser updates the progress element and appends
profile cards as updates arrive, approximately once per second, with no
overlapping requests. It stops polling on completion, partial timeout, failure,
session/job expiry, or an unrecoverable network error. Existing server-rendered
profiles initialize the cursor, avoiding duplicates after a manual page refresh
or when opening a cached completed search. Invalid cursors receive a client
error without exposing job data.

Worker-to-server progress messages should carry profile deltas rather than
repeated full profile snapshots. The job manager keeps only bounded progress
data associated with the existing expiring job; it must not introduce a
separate unbounded history or persistent storage. A final report remains
authoritative and reconciles the accumulated results.

### Security and accessibility

- Every updates request must resolve the job using the current session owner;
  an unknown, expired, or foreign job returns the same not-found response.
- Keep responses `no-store`, validate the cursor and response shape, and do not
  enable cross-origin access.
- Keep scripts external and self-hosted. The Content Security Policy must allow
  scripts and connections from `'self'` only (`script-src 'self'` and
  `connect-src 'self'`, retaining the other existing restrictions); no inline
  scripts, event-handler attributes, CDNs, or new runtime dependencies.
- Construct browser content with DOM APIs and text nodes, never `innerHTML`.
  Continue validating profile and outbound-link URLs as HTTP or HTTPS.
- Preserve useful status announcements and a labeled progress bar for assistive
  technology. Network errors must not silently imply that the search failed or
  start a duplicate search.

### Performance and compatibility

The change targets full-page transfer/render work and repeated progress
serialization. It must preserve the configured site count, connection limit,
timeouts, result cache semantics, and external Maigret search behavior. Search
duration remains dependent on the sites being checked. Measure progress payload
size or serialization work against the current cumulative-snapshot behavior.

### Verification and delivery

Tests cover authorized and unauthorized update access, cursor validation,
incremental and final results, completion/partial/error states, no automatic
page refresh, safe rendering, and the no-JavaScript fallback. Run the existing
test suite, UI verification, performance checks, and browser checks. Update the
English and Portuguese documentation. Deploy only after checks pass; verify the
HTTPS application and health endpoint on the IONOS VPS after deployment.

### Out of scope

Changing Maigret's site selection, search concurrency, timeouts, or matching
semantics; adding persistence, user accounts, third-party frontend code, or
cross-session result access.

## Português (Brasil)

### Objetivo

Permitir acompanhar uma busca do Deeper sem recarregar a página inteira a cada
três segundos. Mostrar novos perfis assim que estiverem disponíveis e manter o
progresso da verificação visível. Reduzir o custo de entrega do progresso sem
prometer que os sites externos responderão mais rápido.

### Comportamento atual

O progresso do Maigret já é coletado pelo worker e armazenado no gerenciador de
buscas privado e em memória. A página de resultados usa atualização automática
do HTML a cada três segundos; assim, cada atualização recria e transfere a
página inteira e todos os perfis. As mensagens de progresso também carregam a
lista acumulada, mesmo quando há pouca informação nova.

### Desenho proposto

Manter o fluxo atual de envio POST seguido de redirecionamento. Substituir a
atualização automática do HTML por melhoria progressiva com um arquivo
JavaScript servido pelo próprio Deeper e um endpoint JSON da mesma origem. A
página continuará renderizada no servidor e oferecerá atualização manual como
alternativa quando JavaScript estiver indisponível.

O endpoint aceitará um cursor inteiro não negativo e limitado e retornará
contadores, estado da busca e somente os novos perfis desde esse cursor. Uma
sequência monotônica identificará cada evento de perfil; sua duração limitada
acompanhará a retenção já existente do trabalho, e o total de eventos não poderá
exceder a quantidade de sites verificados. O navegador atualizará a barra de
progresso e acrescentará os cartões de perfil à página, aproximadamente uma
vez por segundo, sem sobrepor requisições. A consulta periódica será encerrada
quando a busca terminar, expirar parcialmente, falhar, a sessão ou o trabalho
expirar, ou houver um erro de rede irrecuperável. Os perfis já renderizados
pelo servidor inicializarão o cursor para evitar duplicatas após uma
atualização manual ou ao abrir uma busca concluída em cache. Cursores inválidos
receberão erro de cliente sem revelar dados do trabalho.

As mensagens de progresso entre o worker e o servidor devem carregar deltas de
perfis, em vez de repetir snapshots completos. O gerenciador manterá apenas
dados de progresso limitados e associados ao trabalho com expiração já
existente; não haverá histórico separado sem limite nem armazenamento
persistente. O relatório final continuará sendo a fonte autoritativa e
reconciliará os resultados acumulados.

### Segurança e acessibilidade

- Cada consulta deve localizar o trabalho usando o dono da sessão atual; um
  trabalho desconhecido, expirado ou pertencente a outra sessão retornará a
  mesma resposta de não encontrado.
- Manter respostas `no-store`, validar cursor e formato da resposta e não
  habilitar acesso entre origens.
- Scripts externos e servidos pelo próprio projeto. A Política de Segurança de
  Conteúdo permitirá scripts e conexões somente de `'self'` (`script-src 'self'`
  e `connect-src 'self'`, mantendo as demais restrições existentes); sem
  scripts embutidos, atributos de eventos, CDNs ou novas dependências de
  runtime.
- Criar conteúdo no navegador com APIs do DOM e nós de texto, nunca com
  `innerHTML`. Continuar validando URLs de perfis e links externos para HTTP ou
  HTTPS.
- Manter anúncios de estado e uma barra de progresso identificada para
  tecnologias assistivas. Erros de rede não devem sugerir silenciosamente que a
  busca falhou nem iniciar uma busca duplicada.

### Desempenho e compatibilidade

A mudança reduz o trabalho de transferência/renderização da página completa e
a serialização repetida do progresso. Deve preservar quantidade configurada de
sites, limite de conexões, prazos, cache de resultados e comportamento externo
do Maigret. A duração da busca continua dependendo dos sites consultados. Medir
o tamanho dos payloads de progresso ou o custo de serialização em comparação
com os snapshots cumulativos atuais.

### Verificação e entrega

Os testes cobrem acesso autorizado e não autorizado, validação de cursor,
resultados incrementais e finais, estados concluído/parcial/erro, ausência de
atualização automática da página, renderização segura e alternativa sem
JavaScript. Executar a suíte existente, verificação da interface, verificações
de desempenho e testes em navegador. Atualizar a documentação em inglês e
português. Implantar somente após a aprovação das verificações e validar a
aplicação HTTPS e o endpoint de saúde na VPS IONOS.

### Fora de escopo

Alterar seleção de sites do Maigret, concorrência, prazos ou semântica de
correspondência; adicionar persistência, contas de usuário, código frontend de
terceiros ou acesso a resultados entre sessões.
