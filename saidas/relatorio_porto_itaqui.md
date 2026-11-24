# Relatório de simulação - Porto do Itaqui

Simulação de dados sintéticos de embarque e desembarque de cargas.
Porto do Itaqui - São Luís / MA. DECC0294, UFMA, Curso de Administração.
Gerado em 24/11/2026 às 09:59 pelo script simulacao_porto_itaqui.py.

## Aviso importante

Esta base é sintética (inventada com semente aleatória fixa). Ela serve
apenas para exercício de análise de dados e visualização. Não use estes
números para decisões operacionais do porto real sem dados da CODESA/ANTAQ.

## Visão geral da simulação

| Indicador | Valor |
|---|---|
| Período simulado | 90 dias (a partir de 01/08/2026) |
| Navios simulados | 126 |
| Berços do cais simulado | 4 |
| Tempo médio de espera por berço | 478.22 h |
| Mediana de espera por berço | 478.29 h |
| Tempo médio de operação (embarque/desembarque) | 12.69 h |
| Tempo médio total (chegada → desatracação) | 492.84 h |
| Mediana do tempo total | 489.15 h |
| Navios com algum atraso extra | 23 (18.3%) |
| Atraso total médio por navio | 1.06 h |
| Navios que esperaram mais de 12 h por berço | 84.9% |
| Navios com operação acima de 48 h | 6.3% |

## Tempo total médio por tipo de carga

| Tipo de carga | Navios | Espera média (h) | Operação média (h) | Tempo total médio (h) |
|---|---|---|---|---|
| Carga geral | 34 | 506.72 | 16.35 | 524.28 |
| Contêineres | 34 | 475.52 | 14.36 | 492.55 |
| Granel líquido | 28 | 524.53 | 7.21 | 533.40 |
| Granel sólido | 30 | 405.75 | 11.75 | 419.69 |

## Atraso médio por causa (horas por navio)

| Causa | Atraso médio (h) | Navios afetados |
|---|---|---|
| Clima | 0.42 | 7 |
| Equipamento | 0.22 | 4 |
| Mão de obra | 0.09 | 3 |
| Documentação | 0.33 | 10 |

## Por turno de chegada

| Turno | Navios | Tempo total médio (h) |
|---|---|---|
| Manhã | 29 | 469.91 |
| Tarde | 28 | 611.63 |
| Madrugada | 69 | 454.27 |

## Por mês

| Mês | Navios | Tempo total médio (h) |
|---|---|---|
| 08/2026 | 37 | 186.33 |
| 09/2026 | 44 | 897.75 |
| 10/2026 | 45 | 348.95 |

## Principais conclusões da simulação

- O maior componente do tempo total tende a ser a operação em si (embarque/desembarque),
  não apenas a espera por berço.
- Tipo de carga influencia fortemente a duração: carga geral e granel sólido demoram mais.
- Aproximadamente 18.3% dos navios tiveram algum atraso extra além do tempo planejado.
- Clima e documentação são as causas de atraso mais frequentes nesta simulação.

## Limitações

- Dados sintéticos, não reais.
- Modelo de fila simplificado (berços fixos, sem prioridade de atracação).
- Não considera marés, calado dos navios, nem limitações de pilha no pátio.
