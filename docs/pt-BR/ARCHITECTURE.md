# Deeper 0.5.0 — arquitetura das buscas

[English](../ARCHITECTURE.md) | **Português (Brasil)**

O Deeper executa uma aplicação HTTP com gerenciador de tarefas em memória e um
executor limitado compartilhado entre tarefas por usuário e nome completo.
Buscas por usuário usam processos isolados do Maigret; buscas por nome fazem
uma requisição HTTP limitada ao Serper na mesma vaga do executor. A aplicação HTTP cuida
da privacidade por sessão, admissão, agendamento, progresso e resultados
temporários. Cada worker carrega a base do Maigret uma vez e usa uma cópia
independente dos sites em cada busca por usuário.

## Modos e limite do provedor

`GET /?mode=name` seleciona o formulário por nome renderizado no servidor.
`POST /search` mantém o campo legado `username` e acrescenta `mode` e `file_type`;
omitir os campos mantém o comportamento por usuário. O modo por nome exige
`consent=1` antes de enviar nome e filtro ao Serper/Google. Nomes são normalizados
para Unicode NFC e espaços únicos, devem ter pelo menos duas palavras e 2–120
caracteres e aceitam apenas letras, marcas combinantes, espaços, apóstrofos,
hífens e pontos. Entradas brutas excessivas, aspas, controles e operadores de
consulta são rejeitados. Nomes nunca geram usuários presumidos.

A lista de tipos é `any`, `pdf`, `doc`, `docx`, `xls`, `xlsx`, `ppt`, `pptx`,
`odt`, `ods`, `odp`, `rtf`, `txt` e `csv`. A consulta coloca o nome inteiro entre
aspas e acrescenta apenas o operador `filetype:` permitido selecionado. Cada
tarefa por nome sem cache faz exatamente um POST para o endpoint fixo
`https://google.serper.dev/search`, com `num=10`, `gl=br` e `hl=pt-br`. Não há
repetição automática, redirecionamentos, alternativa por scraping, download,
pré-visualização nem acesso à URL dos resultados. Um link externo separado do
Google abre resultados adicionais fora da aplicação.

`SerperSearch.from_env()` carrega `SERPER_API_KEY` de forma privada. A chave não
entra em snapshots de configuração, tarefas, JSONL dos workers, respostas ao
navegador ou logs. `DEEPER_NAME_DAILY_LIMIT` permite 100 chamadas por dia UTC por
processo por padrão, com pelo menos um segundo entre chamadas externas. Reiniciar
zera o contador; é proteção de consumo, não garantia de cobrança para toda a
conta. Não há compra de créditos nem recarga automática. `DEEPER_NAME_TIMEOUT`
usa 12 segundos por padrão e aceita valores finitos de 1 a 30. É um timeout HTTP
normal do `urllib`, não prazo absoluto imposto por processo. Respostas são
limitadas a 1 MiB. Chaves ausentes, cotas esgotadas, erros de rede e payloads
inválidos geram mensagens públicas fixas, sem exceções externas ou resultados
inventados.

## Contrato das referências e limites da evidência

Tarefas por nome retornam até dez referências, com `id` (URL canônica sem
fragmento), `title` (até 300 caracteres), `url` (até 2048), `snippet` (até 1600),
`source` (hostname) e `file_type` inferido da URL ou identificado como
desconhecido/HTML. URLs HTTP(S) inseguras são rejeitadas. URLs duplicadas são
unificadas; títulos ou hosts iguais não. Extensões conhecidas incompatíveis
com o filtro são removidas; tipos desconhecidos continuam não verificados.

As referências são metadados do índice de busca. Consulta com nome exato entre
aspas, extensão e filtro não comprovam identidade, MIME, disponibilidade atual
ou conteúdo do documento. Busca vazia não comprova ausência. Os resultados são
links para avaliação do usuário, sem verificar nem baixar o conteúdo.

## Admissão e agendamento justo

Os limites padrão são duas buscas em execução, 64 tarefas pendentes no total e
duas tarefas pendentes por sessão anônima do navegador. Pendentes são as tarefas
na fila ou em execução. `DEEPER_WORKERS`, `DEEPER_MAX_JOBS` e
`DEEPER_MAX_JOBS_PER_SESSION` configuram esses limites.

Um envio primeiro reutiliza a busca ativa do mesmo modo, valor normalizado e
tipo de arquivo na mesma sessão ou
um resultado bem-sucedido concluído dentro do TTL do cache. A reutilização não
cria outra tarefa e é verificada antes das duas cotas. Erros e resultados
parciais não são reutilizados. Para uma nova tarefa, o limite da sessão é
verificado antes da capacidade global. Tarefas concluídas não contam na cota da
sessão; resultados concluídos mais antigos podem ser descartados para manter o
total de tarefas retidas dentro do limite global.

| Novo envio | Resposta HTTP |
| --- | --- |
| Sessão já tem duas tarefas pendentes | `429 Too Many Requests`, `Retry-After: 5` |
| Capacidade global sem espaço após descartar concluídas | `503 Service Unavailable`, `Retry-After: 5` |
| Aceito ou reutilizado | `303 See Other` para a página privada de resultados |

Quando um worker fica disponível, o gerenciador escolhe a sessão pendente
atendida há mais tempo. Dentro dela, inicia a tarefa pendente mais antiga. O
gerenciador atribui trabalho somente quando há um worker disponível, evitando
que as buscas de uma sessão reservem todas as próximas vezes em uma fila
interna do executor. Buscas em execução terminam normalmente; a justiça escolhe
a próxima tarefa e não interrompe uma busca ativa.

Por exemplo, com um worker, se a sessão A tem A1 em execução e A2 na fila antes
de a sessão B enviar B1, B1 recebe a próxima vez, seguida por A2. Com dois
workers, até duas buscas podem estar em execução quando B chega; B aguarda a
liberação de um worker. A cota por sessão é uma regra de compartilhamento de
capacidade anônima, não um sistema de identidade nem uma limitação robusta
contra bots: clientes podem criar novas sessões. A fila dispensa serviço externo
e registro de IPs.

## Posição na fila e resultados progressivos

O HTML dos resultados e as atualizações da mesma origem informam a posição atual
da tarefa na fila. Snapshots e respostas de atualização incluem
`queue_position`: inteiro positivo para uma tarefa na fila ou `0` quando ela
está em execução ou em estado final. A posição é calculada pela ordem justa
atual. A entrada de outras sessões pode mudá-la; ela não é uma sequência global
de envios nem uma estimativa de tempo.

Páginas pendentes pedem progresso aproximadamente a cada segundo. As
atualizações por usuário usam cursor e retornam novos registros de perfis em
vez de repetir os anteriores. O `search-progress.js` existente trata tarefas por
usuário. Tarefas por nome usam `document-progress.js` separado no mesmo endpoint
privado: cada snapshot contém a lista limitada completa `references`, `mode` e
`file_type`. O navegador remove duplicatas por URL; tarefas por nome não têm
cursor de referências e mantêm o cursor legado de perfis em `0`. Seu
`checked`/`total` conta requisições ao provedor (0/1 ou 1/1), não sites
verificados. Atualizar a página renderiza um snapshot completo no
servidor. A página inicial dispensa JavaScript; sem JavaScript, a página de
resultados oferece atualização manual. Mantêm-se CSRF, respostas `404` para
acesso sem propriedade, cabeçalhos de segurança e `no-store`. Toda consulta de
resultado ou progresso exige a sessão dona da tarefa. Documentos são renderizados
com texto inerte e links validados, acesso por teclado, anúncios educados de
progresso e estados visíveis de vazio, falha e nova tentativa.

## Ciclo de vida de workers e resultados

Workers de usuário iniciam sob demanda, são reciclados após 25 buscas e encerrados após
120 segundos ociosos por padrão. As buscas verificam até 500 sites com
20 conexões, timeout de 10 segundos por site e prazo total de 180 segundos. Um
watchdog pode encerrar um worker bloqueado após esse prazo mais 15 segundos de
inicialização. Os limites e a extração das buscas são independentes do
agendamento justo.

Resultados concluídos com sucesso podem ser reutilizados por 60 segundos na
mesma sessão. As tarefas expiram 15 minutos após a conclusão, com limpeza
periódica em até cinco segundos. Resultados, fila e cache ficam em memória e
desaparecem ao reiniciar; as buscas não criam histórico ou relatórios persistentes.

Execute uma única instância da aplicação HTTP. Instâncias HTTP independentes
teriam tarefas e estado de agendamento separados; compartilhar somente a chave
de sessão não compartilha essas tarefas. `DEEPER_WORKERS` controla as vagas
compartilhadas de busca, não as instâncias HTTP. O limite de recursos padrão do Compose e o
perfil opcional de um worker estão em [Desempenho e armazenamento](PERFORMANCE.md).
