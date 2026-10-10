# Deeper 0.3.0 — desempenho e armazenamento

[English](../PERFORMANCE.md) | **Português (Brasil)**

As medições históricas abaixo comparam as buscas e o armazenamento das versões
0.1.0 e 0.2.0. A medição de payloads incrementais da versão 0.3.0 aparece em
seção separada; são dados sintéticos locais, não tempos de resposta de sites
públicos.

## Histórico: busca e armazenamento de 0.1.0 a 0.2.0

Medições feitas em 9 de outubro de 2026, Linux x86_64, Python 3.12.14. O
principal ganho foi nas buscas seguintes em um processo já carregado.

| Medida | 0.1.0 | 0.2.0 |
| --- | ---: | ---: |
| Primeira busca fria, uma amostra | 2.593s | 2.521s |
| Buscas seguintes, mediana de quatro amostras | 2.705s | 1.130s |
| Repetição do username na mesma sessão | 2.419s | 0.347ms (cache) |
| Requisições HTTP na repetição | 500 | 0 |
| Processos criados, cinco buscas + repetição | 6 | 1 |
| Pico de RSS do worker | 66.2 MiB | 66.3 MiB |
| Arquivos instalados em site-packages | 193.7 MiB | 128.3 MiB |

O tempo das buscas seguintes foi **58,2% menor**. Os arquivos instalados ficaram
**33,8% menores**, uma redução lógica de 65,4 MiB. MiB = 1.048.576 bytes. São
amostras locais, não prazos garantidos para sites públicos.

## Progresso incremental na versão 0.3.0

Medição feita em 10 de outubro de 2026 com Python 3.12.12, Linux x86_64
(kernel 7.2.9, glibc 2.41), Maigret 0.6.6, 500 sites ranqueados, 20 conexões,
um worker e fixture HTTP local com atraso de 5ms. Cada uma das duas buscas
retornou 50 perfis CLAIMED, 400 sites ausentes e 50 verificações inconclusivas.

| Medida | Observado |
| --- | ---: |
| Mensagens de progresso em execução, duas buscas | 14 |
| Payload JSON incremental total | 12.797 bytes |
| Referência com snapshot cumulativo | 37.373 bytes |
| Redução dos payloads de progresso | 65,8% |
| Busca sintética fria / segunda | 4,303s / 3,249s |
| Repetição de resultado em cache | 0,305ms, 0 requisições HTTP |
| Pico de RSS de um worker | 96,6 MiB |

Os tamanhos comparam os eventos incrementais emitidos com uma referência que
repete todos os perfis acumulados em cada evento correspondente. Em uma amostra
separada de 100 sites, com apenas quatro mensagens de progresso, os deltas
somaram 434 bytes contra 410 bytes cumulativos; aquela amostra esparsa não teve
ganho. A redução depende da quantidade e do tamanho dos eventos. Essas medições
não aceleram as verificações externas do Maigret nem preveem a latência de sites
públicos.

## Método e integridade

- O benchmark usa o **Maigret oficial 0.6.6**, seleção e ranking oficiais da
  base, 500 sites e 20 conexões. Somente os endpoints dos sites selecionados
  são substituídos por fixtures locais. O motor, parser e ciclo de processos
  são reais.
- O servidor HTTP local responde após 5ms. Cada busca retorna 50 perfis
  CLAIMED, 400 sites ausentes e 50 verificações inconclusivas. A comparação
  histórica entre 0.1.0 e 0.2.0 produziu contagens equivalentes nas cinco
  execuções; a amostra de payloads 0.3.0 usou duas execuções. Nenhum username de
  pessoa real foi pesquisado.
- A primeira busca inclui importação e carregamento da base. As quatro
  seguintes usam usernames diferentes; o ganho vem da reutilização do worker,
  não do cache de resultados.
- A repetição final usa o mesmo username e sessão: a versão 0.2.0 reutiliza um
  resultado concluído por até 60 segundos. A medida inclui submissão/snapshot do
  backend, **não** rede ou renderização do navegador. Cache não é uma nova
  verificação.
- O RSS é medido com `resource.getrusage(RUSAGE_SELF).ru_maxrss` em um worker
  Linux. Não inclui servidor, fixtures, fila ou tarefas em cache. Workers
  aquecidos mantêm essa memória até serem reciclados ou ficarem ociosos; o
  padrão permite dois workers simultâneos.
- O disco é a soma dos tamanhos de arquivos regulares, excluindo links
  simbólicos, em ambientes Python 3.12 limpos usando o mesmo lock. A base usa
  instalação pip normal da versão 0.1.0; o novo runtime usa `--no-compile`,
  versão 0.2.0 e o aparador. Código, base e licenças são preservados. Após o
  aparo, um smoke check usa o Maigret real com HTTP local e verifica health, HTML
  e CSS do wheel instalado.
- As contagens não incluem imagens base de Python/Linux, overhead de blocos,
  downloads, camadas da imagem ou cache de build. **A imagem Docker 0.3.0 não foi
  construída localmente:** a configuração Compose foi validada; build e tamanho
  da imagem ficam para a implantação na IONOS. Um build também requer espaço
  temporário adicional.

## Reprodução

Com as árvores de versão necessárias e dependências instaladas, execute em Linux:

```sh
python scripts/benchmark.py --project /caminho/deeper-0.1.0 --output /caminho/baseline.json
python scripts/benchmark.py --project /caminho/deeper-0.2.0 --output /caminho/optimized.json
python scripts/benchmark.py --project /caminho/deeper-0.3.0 --output /caminho/progress.json --runs 2 --sites 500
```

Execute em sequência para evitar sobreposição entre cenários. O script valida as
contagens e encerra todos os processos ao terminar. Para medir a imagem na VPS,
use `docker image inspect deeper:0.3.0 --format '{{.Size}}'` e
`docker system df`. O Deeper não executa comandos de limpeza global.

## Como o armazenamento é controlado

O runtime não precisa de banco, histórico, build de frontend ou navegador. O
Docker instala com hashes e sem cache de download; uma etapa final copia o
ambiente aparado. Testes de dependências não utilizados, bytecode, traduções do
`pycountry` sem uso e ferramentas de instalação são removidos; bibliotecas
necessárias e seus arquivos de licença são preservados.

`compose.yaml` rotaciona logs em três arquivos de 2 MB (aproximadamente 6 MB
mais overhead), usa filesystem somente leitura e limita `/tmp` a um tmpfs de
32 MB. Esses limites valem para o container Deeper, não para logs do proxy ou de
outros serviços. O tmpfs usa memória e pode ser paginado para swap pelo host.
Versões anteriores de imagens Docker e camadas de build continuam ocupando
espaço.

Referências oficiais da configuração: [rotação json-file](https://docs.docker.com/engine/logging/drivers/json-file/),
[montagens tmpfs](https://docs.docker.com/engine/storage/tmpfs/) e
[cache de build](https://docs.docker.com/build/cache/).
