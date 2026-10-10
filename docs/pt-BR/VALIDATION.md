# Deeper 0.3.0: validação

[English](../VALIDATION.md) | **Português (Brasil)**

Data: 10 de outubro de 2026. As buscas automatizadas abaixo usam apenas fixtures HTTP sintéticas locais; nenhum username de sites públicos foi consultado. A implantação real na IONOS é uma etapa de release separada e não é declarada neste relatório local.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Suíte completa Python 3.12.12 | 84 testes passaram em 10,92s. |
| Build do wheel | `deeper_maigret-0.3.0-py3-none-any.whl`; inclui `search-progress.js` e os dois arquivos de licença. |
| Smoke test do wheel instalado | Venv novo fora do repositório; versão 0.3.0, Maigret 0.6.6, base oficial, busca HTTP local, health, HTML, CSS e JavaScript passaram. |
| Maigret real com HTTP local | 3 verificações concluídas, 1 inconclusiva e 1 perfil sintético encontrado. |
| Resultados incrementais no navegador | Chromium 153.0.8010.47, desktop 1440×900 e mobile 390×844; primeiro perfil apareceu em 1,796s / 1,872s enquanto a fixture lenta ainda aguardava; progresso 1/2, no máximo uma requisição simultânea, nenhum reload ou problema no console. |
| Reconciliação final e status visível | Perfis corrigidos substituíram cartões antigos, perfis retirados desapareceram, conclusão e recuperação de busca indisponível ficaram visíveis e o estado busy foi limpo quando o polling parou. |
| Alternativa sem JavaScript | Busca permaneceu em HTML renderizado no servidor com link de atualização manual; nenhuma requisição de script no navegador com JavaScript desativado. |
| Renderização segura e recuperação | Conteúdo semelhante a HTML permaneceu inerte, links `javascript:` foram rejeitados, links seguros usaram `noopener noreferrer` e o polling parou após três respostas 503. |
| Acessibilidade e layout | Movimento reduzido e texto a 200% em 320px passaram sem overflow horizontal. |
| Benchmark de payloads | Duas buscas sintéticas de 500 sites: 14 mensagens, 14.993 bytes de JSONL incremental no formato do worker vs. 42.984 bytes da referência cumulativa (65,1% menor); primeira / segunda busca em 4,150s / 3,008s. |
| Configuração Compose | `docker compose config --quiet` passou. Não foi feito build local da imagem; a implantação fará essa verificação separadamente. |

O benchmark usa Linux x86_64, Python 3.12.12, Maigret 0.6.6, 20 conexões, um worker e fixture HTTP local com atraso de 5ms. Esses tempos e tamanhos de payload não preveem a latência de sites públicos; o Deeper não controla a resposta de plataformas externas. [`PERFORMANCE.md`](PERFORMANCE.md) registra o método e a amostra menor de 100 sites, na qual quatro eventos esparsos tiveram um payload incremental ligeiramente maior que a referência cumulativa.

## Reprodução

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m build --wheel
LD_LIBRARY_PATH=/caminho/do/profile/guix/lib .venv/bin/python tests/verify_ui.py --browser /caminho/do/chromium
.venv/bin/python scripts/benchmark.py --project /caminho/deeper --output /tmp/progress.json --runs 2 --sites 500
```

Execute o smoke test do wheel instalado em um venv novo com as dependências de runtime fixadas por hashes, a partir de uma pasta fora do repositório. `tests/verify_installation.py` verifica o caminho do módulo instalado, as versões do pacote e do motor, health, base oficial de sites, busca HTTP local, HTML, CSS e o JavaScript empacotado.

## Limitações

- Sites públicos não foram consultados. Rede, bloqueios e respostas das plataformas podem dominar o tempo de busca. Uma busca fria ainda carrega a base do Maigret.
- A suíte 0.3.0 foi executada em Python 3.12.12; Python 3.11 não foi revalidado nesta release. A validação da versão 0.2.0 é histórica e não substitui uma execução da 0.3.0 em Python 3.11.
- Tarefas e cache permanecem em memória, são privados à sessão e expiram conforme o limite configurado. Execute uma única instância HTTP.
- Verificações incompatíveis com o username ou que exijam protocolos não configurados podem ser ignoradas pelo Maigret e contadas entre os itens processados.
- Windows não foi testado; a verificação SIGTERM é específica de Unix.
