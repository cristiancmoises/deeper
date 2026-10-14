# Deeper 0.4.0 — arquitetura das buscas

[English](../ARCHITECTURE.md) | **Português (Brasil)**

O Deeper executa uma aplicação HTTP com gerenciador de tarefas em memória e um
pool limitado de processos isolados de busca do Maigret. A aplicação HTTP cuida
da privacidade por sessão, admissão, agendamento, progresso e resultados
temporários. Cada worker carrega a base do Maigret uma vez e usa uma cópia
independente dos sites em cada busca.

## Admissão e agendamento justo

Os limites padrão são duas buscas em execução, 64 tarefas pendentes no total e
duas tarefas pendentes por sessão anônima do navegador. Pendentes são as tarefas
na fila ou em execução. `DEEPER_WORKERS`, `DEEPER_MAX_JOBS` e
`DEEPER_MAX_JOBS_PER_SESSION` configuram esses limites.

Um envio primeiro reutiliza a busca ativa do mesmo usuário na mesma sessão ou
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
atualizações usam cursor e retornam novos registros de perfis em vez de repetir
todos os anteriores. Atualizar a página renderiza um snapshot completo no
servidor. A página inicial dispensa JavaScript; sem JavaScript, a página de
resultados oferece atualização manual. Toda consulta de resultado ou progresso
exige a sessão do navegador que é dona da tarefa.

## Ciclo de vida de workers e resultados

Workers iniciam sob demanda, são reciclados após 25 buscas e encerrados após
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
de sessão não compartilha essas tarefas. `DEEPER_WORKERS` controla os processos
de busca, não as instâncias HTTP. O limite de recursos padrão do Compose e o
perfil opcional de um worker estão em [Desempenho e armazenamento](PERFORMANCE.md).
