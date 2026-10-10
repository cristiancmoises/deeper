# Deeper 0.3.0

[English](README.md) | **Português (Brasil)**

Experimente a aplicação: **[deeper.securityops.co](https://deeper.securityops.co)**

Deeper é uma interface web independente e minimalista para o **Maigret 0.6.6**.
Informe um nome de usuário para verificar páginas de perfis publicamente
acessíveis em sites compatíveis. Nomes iguais não provam que os perfis pertencem
à mesma pessoa; avalie cada resultado no contexto. O Deeper não faz buscas
recursivas, não usa cookies autenticados de plataformas e não contorna controles
de acesso.

A interface tem fundo preto, detalhes em ciano e título animado em CSS. A página
inicial da busca é renderizada no servidor sem JavaScript. Enquanto há uma
pesquisa pendente, a página de resultados carrega um único script da mesma
origem para acrescentar perfis e atualizar o progresso sem recarregar a página
inteira. Sem JavaScript, o HTML continua funcional e há um link de atualização
manual. Os resultados são privados à sessão do navegador e ficam em memória;
a aplicação não tem banco de dados, histórico persistente nem relatórios em disco.

## Capturas de tela

Tela inicial de pesquisa:

![Tela inicial de pesquisa do Deeper](docs/images/deeper-search-start.png)

Pesquisa em andamento com resultados:

![Progresso e resultados de uma busca no Deeper](docs/images/deeper-search-results.png)

Os nomes de usuário e correspondências exibidos são exemplos, não uma
confirmação de identidade.

## Deploy rápido com Docker Compose

Requisitos: Git, Docker Engine e o plugin Docker Compose. A configuração padrão
usa `127.0.0.1:8080`, sem expor o serviço diretamente à internet pública.

```sh
git clone https://github.com/cristiancmoises/deeper.git
cd deeper
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/health
```

Abra <http://127.0.0.1:8080>. Acompanhe a inicialização com
`docker compose logs -f deeper` e pare o serviço com `docker compose down`.
O repositório público do código está no
[GitHub](https://github.com/cristiancmoises/deeper).

Para uma VPS pequena, crie um arquivo `.env` local ao lado de `compose.yaml`:

```dotenv
DEEPER_WORKERS=1
DEEPER_MAX_JOBS=16
```

Depois execute `docker compose up -d --build`. Para disponibilizar sua própria
instância publicamente, coloque um proxy reverso com HTTPS na frente do Deeper
e defina `DEEPER_SECURE_COOKIE=1` no `.env`. Mantenha o app em loopback quando o
proxy estiver no mesmo host. Se o proxy exigir um bind fora do loopback, restrinja
o acesso com firewall; não exponha a porta HTTP sem TLS diretamente à internet.

## O que há na versão 0.3.0

- Novos perfis e o progresso dos sites aparecem durante a busca; cada resposta
  leva somente os perfis após o cursor atual do navegador. Os limites de sites,
  concorrência e prazos do motor de busca não mudaram.
- Workers isolados de busca são reutilizados: a base do Maigret é carregada uma
  vez por processo, com uma cópia independente dos sites para cada pesquisa.
  Processos nascem sob demanda, são reciclados após 25 buscas e encerrados após
  120 segundos ociosos.
- Buscas concluídas com o mesmo usuário e sessão são reutilizadas por até
  60 segundos. A página mostra a idade do resultado; erros e resultados parciais
  não são reutilizados.
- Resultados e cache ficam em memória. Tarefas expiradas são removidas
  periodicamente, mesmo sem novas requisições.
- O build Docker instala sem cache de downloads ou bytecode e leva apenas o
  runtime instalado para a imagem final. Testes de dependências não usados,
  traduções do `pycountry` e ferramentas de instalação são removidos; os dados
  do motor e os arquivos de licença são preservados.
- Os logs rotacionam em três arquivos de 2 MB. O filesystem do container é
  somente leitura e `/tmp` usa tmpfs de 32 MB. As buscas não são persistidas em
  volumes Docker.

As medições e o método estão em
[`docs/pt-BR/PERFORMANCE.md`](docs/pt-BR/PERFORMANCE.md). O tamanho da imagem Docker e o
desempenho em plataformas externas precisam ser medidos no seu ambiente. Builds
também usam armazenamento temporário e cache do Docker; um runtime menor não
elimina esse custo. Consulte o uso local com `docker system df` e
`docker image inspect deeper:0.3.0 --format '{{.Size}}'`. O Deeper não executa
limpeza global do Docker ou da VPS.

## Instalação Python

Python **3.11 e 3.12** foram validados. Instale as dependências fixadas com
hashes e execute a aplicação:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir --no-compile --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-cache-dir --no-compile --no-deps .
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m deeper
```

Não é necessário ativar o ambiente no fish. No Windows, use
`.venv\Scripts\python.exe`. `scripts/slim_runtime.py` serve exclusivamente
para o runtime Docker dedicado do Deeper: ele remove o instalador pip e não deve
ser executado em um ambiente compartilhado.

Para definir host e porta:

```sh
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m deeper --host 0.0.0.0 --port 8080
```

`/health` informa se o pacote Maigret está disponível; não verifica a conexão
com cada plataforma. Os comandos acima instalam o pacote a partir do checkout
atual, após instalar as dependências de runtime fixadas.

## Buscas, limites e atualização dos resultados

O padrão habilita até **500 sites**, **20 conexões** por busca, **duas buscas
simultâneas**, timeout de **10 segundos por site** e prazo de **180 segundos
por busca**. Um watchdog encerra processos bloqueados após o prazo mais
15 segundos de inicialização. Reutilizar workers reduz o custo de inicialização;
não acelera a resposta de sites externos. Uma busca fria ainda paga o custo de
carregar a base.

Enquanto uma busca está pendente, novos perfis são acrescentados e o progresso é
atualizado aproximadamente a cada segundo, sem recarregar a página inteira. Se
JavaScript estiver desativado, use o link manual **Atualizar** para obter o HTML
mais recente; isso não inicia outra busca. Clique no título para voltar ao início.
Se repetir um usuário já pesquisado na mesma sessão em até 60 segundos, a página
mostra a idade do resultado; depois desse prazo, uma nova busca é iniciada. Use
`DEEPER_CACHE_TTL=0` para desativar a reutilização após conclusão. Os resultados
preservam a distinção entre CLAIMED, ausente e inconclusivo.

As tarefas são privadas à sessão e expiram 15 minutos após a conclusão, com
limpeza periódica em até cinco segundos. A fila e o uso de memória são limitados
pela quantidade de tarefas; resultados concluídos mais antigos podem ser
descartados para liberar capacidade. Workers aquecidos mantêm memória até serem
encerrados por ociosidade ou reciclagem. Reiniciar limpa tarefas e cache; sem
chave persistente, também invalida as sessões.

Como as tarefas ficam em memória, execute uma **única instância HTTP**;
`DEEPER_WORKERS` controla a concorrência das buscas. As sessões exigem cookies.
Não há busca recursiva, API de IA, suporte a cookies autenticados de plataformas
ou mecanismo de bypass. Verificações que exigem DNS/Tor/I2P sem configuração ou
formato incompatível de nome de usuário podem ser ignoradas pelo Maigret e
contadas como verificações processadas.

## Configuração

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `DEEPER_TOP_SITES` | `500` | Limite de sites; `0` verifica todos os habilitados. |
| `DEEPER_SITE_TIMEOUT` | `10` | Segundos por site. |
| `DEEPER_SEARCH_TIMEOUT` | `180` | Prazo da pesquisa em segundos. |
| `DEEPER_CONNECTIONS` | `20` | Conexões por pesquisa. |
| `DEEPER_WORKERS` | `2` | Pesquisas simultâneas. |
| `DEEPER_MAX_JOBS` | `64` | Tarefas em memória, incluindo fila e cache. |
| `DEEPER_RETENTION` | `900` | Segundos para manter uma tarefa concluída. |
| `DEEPER_CACHE_TTL` | `60` | Reutiliza resultados na mesma sessão; `0` desativa. |
| `DEEPER_WORKER_MAX_JOBS` | `25` | Recicla o processo após esse número de buscas. |
| `DEEPER_WORKER_IDLE_TIMEOUT` | `120` | Encerra um processo ocioso após esse prazo. |
| `DEEPER_SECRET_KEY` | aleatória ao iniciar | Chave de sessão opcional para persistir entre reinícios. |
| `DEEPER_SECURE_COOKIE` | `0` | Defina `1` quando servir exclusivamente por HTTPS. |

O Compose aceita configurações do ambiente ou de um `.env` local. Alterar limite
de sites, extração, timeouts ou conexões pode afetar cobertura e confiabilidade;
os padrões originais de pesquisa foram preservados nesta otimização.

## Validação e licença

[`docs/pt-BR/VALIDATION.md`](docs/pt-BR/VALIDATION.md) descreve a validação da versão 0.3.0. A
suíte usa o Maigret real com fixtures HTTP locais e perfis sintéticos.
`tests/verify_ui.py` usa Playwright como ferramenta externa de QA; ele não
adiciona scripts à página.

O Deeper é uma interface independente, não é o projeto oficial Maigret. O
backend é o **Maigret 0.6.6**, projeto sob licença MIT de **Soxoj**. Agradecemos
ao Soxoj por disponibilizar o projeto sob a licença MIT. Consulte
[`THIRD_PARTY_NOTICES.pt-BR.md`](THIRD_PARTY_NOTICES.pt-BR.md), [`LICENSE`](LICENSE)
e [`LICENSE-MAIGRET`](LICENSE-MAIGRET) para créditos e termos das licenças.
