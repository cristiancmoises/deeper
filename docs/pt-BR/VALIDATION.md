# Deeper 0.2.0: validação

[English](../VALIDATION.md) | **Português (Brasil)**

Data: 9 de outubro de 2026. A otimização foi aplicada sobre o pacote Deeper
0.1.0 verificado por SHA256. Esta validação não acessou nem publicou na VPS.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Suíte Python 3.12.14 | 63 testes passaram. |
| Suíte Python 3.11.17, dependências instaladas com hashes | 63 testes passaram. |
| Maigret real com HTTP local | Found/ausente/unknown distintos; fonte/espelho contado uma vez. |
| Cache por sessão | Reutilização, sessão diferente, TTL expirado/desativado e bypass de erro/parcial passaram. |
| Limpeza periódica | Tarefas expiradas em memória removidas sem visitas à página. |
| Workers reais | PID/base reutilizados, sites independentes, reciclagem, ociosidade, EOF, prazo e encerramento passaram. |
| SIGTERM real | Processo filho encerrado e coletado. |
| Segurança | Sessão privada, CSRF, escape e links somente HTTP/HTTPS preservados. |
| UI sem JavaScript | Tecla Enter, desktop 1440×900 e mobile 390×844; zero scripts ou requisições de script. |
| Acessibilidade | Movimento reduzido e texto a 200% em 320px sem overflow. |
| Benchmark | 500 sites, 20 conexões, mesmo ranking e respostas locais; relatórios equivalentes. |
| Aparador do runtime | Preserva código/dados/licenças e não segue links para fora da raiz. |

[`PERFORMANCE.md`](PERFORMANCE.md) distingue buscas frias, processos
reutilizados, hits de cache e bytes instalados. Perfis e endpoints da validação
eram sintéticos e locais.

## Reprodução

```sh
python -m pytest -q
python -m build --wheel
python tests/verify_ui.py --browser /caminho/do/chromium
python scripts/benchmark.py --project /caminho/deeper --output /caminho/resultado.json
```

Execute `tests/verify_installation.py` com o interpretador Python do ambiente
que recebeu o wheel, a partir de uma pasta fora do projeto. O script verifica o
caminho do módulo instalado, versão 0.2.0, base oficial, busca HTTP local,
endpoint de health, HTML e CSS.

O benchmark usa `resource.getrusage` no Linux para observar o pico de RSS do
worker; isso não mede toda a memória do servidor ou da VPS. A validação visual
usou Chromium 153.0.8010.0 com JavaScript desativado. Playwright e esse navegador
não fazem parte do runtime Docker, e a página não entrega JavaScript.

## Limitações

- Docker não estava instalado neste ambiente: build, execução e tamanho final da
  imagem **não foram medidos**. Os números de disco referem-se aos arquivos de
  `site-packages`, sem base Python, camadas Docker ou cache de build.
- Sites públicos não foram consultados. Rede, bloqueios e respostas das
  plataformas podem dominar o desempenho. A busca fria ainda carrega a base do
  Maigret.
- O cache pode servir dados obtidos até 60 segundos antes; a página mostra a
  idade. Somente buscas concluídas na mesma sessão são reutilizadas. TTL zero
  desativa essa reutilização.
- Processos reutilizados mantêm RAM até reciclagem ou até 120 segundos ociosos;
  a varredura periódica ocorre em até cinco segundos. O número de tarefas limita
  a retenção; ainda é necessária uma única instância HTTP.
- Verificações incompatíveis com o username ou que exijam protocolos não
  configurados podem ser ignoradas pelo Maigret e contadas entre os itens
  processados.
- Windows não foi testado. A verificação SIGTERM é específica de Unix.
