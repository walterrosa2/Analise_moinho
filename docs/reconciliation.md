# Reconciliação — modelo calculado × fonte gerencial

> Gerado por `scripts/gen_docs.py` a partir de `app.reconciliation_result`.

**Regra inegociável:** nenhum dado é ajustado para 'bater'. Divergência acima da
tolerância permanece marcada como `DIVERGENTE` até ser explicada.

---

## Mapeamento descoberto

O relatório 161 não documenta o significado de seus tipos. O confronto numérico
estabeleceu a correspondência:

| `TIPO` no 161 | Equivale no modelo | Evidência (2023) |
|---|---|---|
| `REALIZADO` | **vendas brutas** (sem devolução) | R$ 144,44 mi / 51.171 t ↔ R$ 144,44 mi / 51.172 t |
| `REAL.-DEVOLUÇÃO` | **receita líquida** (com devolução) | R$ 142,18 mi / 50.484 t ↔ R$ 142,18 mi / 50.484 t |
| `DEVOLUÇÃO` | devoluções (positivo na fonte, negativo no modelo) | R$ 2,26 mi ↔ −R$ 2,26 mi |

Mapear `REALIZADO` para o líquido — a leitura intuitiva do nome — produzia ~2,3% de
divergência sistemática em todos os meses.

---

## Resultado por escopo

| Escopo | Métrica | Situação | Pontos | Divergência média | Máxima |
|---|---|---|---|---|---|
| `161_ANUAL` | receita_liquida | DIVERGENTE | 8 | 2,28% | 3,16% |
| `161_ANUAL` | receita_liquida | OK | 8 | 0,16% | 0,49% |
| `161_ANUAL` | volume_liquido_t | DIVERGENTE | 11 | 1,29% | 2,17% |
| `161_ANUAL` | volume_liquido_t | OK | 5 | 0,27% | 0,43% |
| `161_MENSAL_TOTAL` | receita_liquida | OK | 43 | 0,06% | 0,22% |
| `161_MENSAL_TOTAL` | volume_liquido_t | OK | 43 | 0,04% | 0,15% |
| `161_OUTROS` | acordos | SEM_FONTE | 43 | —% | —% |
| `161_OUTROS` | comissao | DIVERGENTE | 43 | 1,86% | 4,12% |
| `161_OUTROS` | frete_cif | DIVERGENTE | 43 | 15,96% | 39,38% |
| `161_OUTROS` | frete_fob | OK | 3 | 0,00% | 0,00% |
| `161_OUTROS` | frete_fob | SEM_FONTE | 40 | —% | —% |
| `161_OUTROS` | icms | DIVERGENTE | 43 | 247,09% | 302,96% |
| `161_OUTROS` | substituicao | DIVERGENTE | 35 | 2,75% | 22,18% |
| `161_OUTROS` | substituicao | OK | 8 | 0,33% | 0,44% |
| `161_REALIZADO` | receita_bruta | DIVERGENTE | 83 | 2,52% | 7,45% |
| `161_REALIZADO` | receita_bruta | OK | 89 | 0,12% | 0,49% |
| `161_REALIZADO` | volume_bruto_t | DIVERGENTE | 104 | 1,59% | 5,13% |
| `161_REALIZADO` | volume_bruto_t | OK | 68 | 0,15% | 0,48% |
| `161_REAL_DEVOLUÇÃO` | receita_liquida | DIVERGENTE | 79 | 2,65% | 7,34% |
| `161_REAL_DEVOLUÇÃO` | receita_liquida | OK | 93 | 0,14% | 0,49% |
| `161_REAL_DEVOLUÇÃO` | volume_liquido_t | DIVERGENTE | 100 | 1,66% | 5,14% |
| `161_REAL_DEVOLUÇÃO` | volume_liquido_t | OK | 72 | 0,17% | 0,48% |

---

## Conclusão

A reconciliação mensal total fecha em **86/86 pontos dentro da
tolerância de 0,5%**, com divergência média de **0,05%**.

A divergência que aparece ao quebrar por classificação vem exclusivamente da regra
produto → categoria, ainda `PROVISIONAL` (ver `docs/open_questions.md`, Q-12 e Q-14).

As métricas de `161 OUTROS` (`Vr ICMS`, `Vr Comissão`) não são reproduzíveis pela
base transacional atual — a hipótese e o que destravaria estão em Q-13.

---

## Detalhe mensal (total, sem quebra por classificação)

| Período | Métrica | Fonte (161) | Modelo | Diferença % | Situação |
|---|---|---|---|---|---|
| 2023-01 | receita_liquida | 9.023.469,73 | 9.023.469,71 | -0,00% | OK |
| 2023-01 | volume_liquido_t | 3.014,36 | 3.014,36 | -0,00% | OK |
| 2023-02 | receita_liquida | 10.397.697,60 | 10.397.697,57 | -0,00% | OK |
| 2023-02 | volume_liquido_t | 3.140,93 | 3.140,92 | -0,00% | OK |
| 2023-03 | receita_liquida | 14.564.073,00 | 14.561.936,41 | -0,01% | OK |
| 2023-03 | volume_liquido_t | 4.620,21 | 4.619,73 | -0,01% | OK |
| 2023-04 | receita_liquida | 11.246.608,79 | 11.246.611,06 | 0,00% | OK |
| 2023-04 | volume_liquido_t | 3.558,79 | 3.558,79 | 0,00% | OK |
| 2023-05 | receita_liquida | 14.520.762,24 | 14.523.256,19 | 0,02% | OK |
| 2023-05 | volume_liquido_t | 4.901,36 | 4.902,14 | 0,02% | OK |
| 2023-06 | receita_liquida | 12.533.187,98 | 12.536.677,66 | 0,03% | OK |
| 2023-06 | volume_liquido_t | 4.193,45 | 4.194,59 | 0,03% | OK |
| 2023-07 | receita_liquida | 11.227.930,65 | 11.230.963,19 | 0,03% | OK |
| 2023-07 | volume_liquido_t | 3.842,56 | 3.843,48 | 0,02% | OK |
| 2023-08 | receita_liquida | 12.884.696,89 | 12.878.403,49 | -0,05% | OK |
| 2023-08 | volume_liquido_t | 4.869,89 | 4.868,64 | -0,03% | OK |
| 2023-09 | receita_liquida | 11.046.352,61 | 11.038.359,72 | -0,07% | OK |
| 2023-09 | volume_liquido_t | 3.969,19 | 3.967,41 | -0,04% | OK |
| 2023-10 | receita_liquida | 10.655.346,79 | 10.657.955,50 | 0,02% | OK |
| 2023-10 | volume_liquido_t | 4.322,51 | 4.323,88 | 0,03% | OK |
| 2023-11 | receita_liquida | 13.420.023,00 | 13.414.541,58 | -0,04% | OK |
| 2023-11 | volume_liquido_t | 5.472,18 | 5.470,61 | -0,03% | OK |
| 2023-12 | receita_liquida | 10.662.232,19 | 10.669.761,21 | 0,07% | OK |
| 2023-12 | volume_liquido_t | 4.578,96 | 4.579,86 | 0,02% | OK |
| 2024-01 | receita_liquida | 12.087.760,67 | 12.086.294,40 | -0,01% | OK |
| 2024-01 | volume_liquido_t | 4.928,33 | 4.927,86 | -0,01% | OK |
| 2024-02 | receita_liquida | 10.375.101,34 | 10.371.634,11 | -0,03% | OK |
| 2024-02 | volume_liquido_t | 4.133,12 | 4.132,07 | -0,03% | OK |
| 2024-03 | receita_liquida | 12.136.531,54 | 12.117.235,03 | -0,16% | OK |
| 2024-03 | volume_liquido_t | 4.869,72 | 4.863,06 | -0,14% | OK |
| 2024-04 | receita_liquida | 12.532.366,97 | 12.555.688,04 | 0,19% | OK |
| 2024-04 | volume_liquido_t | 5.296,65 | 5.304,44 | 0,15% | OK |
| 2024-05 | receita_liquida | 15.142.527,50 | 15.133.996,09 | -0,06% | OK |
| 2024-05 | volume_liquido_t | 6.255,61 | 6.252,90 | -0,04% | OK |
| 2024-06 | receita_liquida | 12.429.587,82 | 12.441.254,70 | 0,09% | OK |
| 2024-06 | volume_liquido_t | 4.977,49 | 4.981,08 | 0,07% | OK |
| 2024-07 | receita_liquida | 14.535.427,68 | 14.531.055,64 | -0,03% | OK |
| 2024-07 | volume_liquido_t | 5.293,37 | 5.291,70 | -0,03% | OK |
| 2024-08 | receita_liquida | 13.431.070,35 | 13.401.143,67 | -0,22% | OK |
| 2024-08 | volume_liquido_t | 5.416,12 | 5.411,76 | -0,08% | OK |
| 2024-09 | receita_liquida | 14.016.915,96 | 14.038.744,84 | 0,16% | OK |
| 2024-09 | volume_liquido_t | 5.235,26 | 5.238,18 | 0,06% | OK |
| 2024-10 | receita_liquida | 10.547.537,06 | 10.542.973,36 | -0,04% | OK |
| 2024-10 | volume_liquido_t | 4.157,16 | 4.155,71 | -0,03% | OK |
| 2024-11 | receita_liquida | 12.316.319,08 | 12.309.723,73 | -0,05% | OK |
| 2024-11 | volume_liquido_t | 4.644,43 | 4.643,54 | -0,02% | OK |
| 2024-12 | receita_liquida | 11.470.355,32 | 11.485.412,69 | 0,13% | OK |
| 2024-12 | volume_liquido_t | 4.402,05 | 4.405,54 | 0,08% | OK |
| 2025-01 | receita_liquida | 12.118.905,22 | 12.095.391,00 | -0,19% | OK |
| 2025-01 | volume_liquido_t | 4.670,21 | 4.663,89 | -0,14% | OK |
| 2025-02 | receita_liquida | 12.188.455,87 | 12.194.414,44 | 0,05% | OK |
| 2025-02 | volume_liquido_t | 4.646,84 | 4.649,07 | 0,05% | OK |
| 2025-03 | receita_liquida | 11.664.718,11 | 11.666.149,19 | 0,01% | OK |
| 2025-03 | volume_liquido_t | 4.295,33 | 4.296,46 | 0,03% | OK |
| 2025-04 | receita_liquida | 8.520.842,06 | 8.522.237,05 | 0,02% | OK |
| 2025-04 | volume_liquido_t | 3.007,39 | 3.009,19 | 0,06% | OK |
| 2025-05 | receita_liquida | 14.009.511,17 | 14.003.923,08 | -0,04% | OK |
| 2025-05 | volume_liquido_t | 5.137,29 | 5.135,27 | -0,04% | OK |
| 2025-06 | receita_liquida | 12.018.320,93 | 12.038.465,64 | 0,17% | OK |
| 2025-06 | volume_liquido_t | 4.591,32 | 4.597,60 | 0,14% | OK |
| 2025-07 | receita_liquida | 12.923.777,24 | 12.928.919,83 | 0,04% | OK |
| 2025-07 | volume_liquido_t | 4.986,44 | 4.987,54 | 0,02% | OK |
| 2025-08 | receita_liquida | 13.377.915,44 | 13.370.440,37 | -0,06% | OK |
| 2025-08 | volume_liquido_t | 5.218,87 | 5.218,33 | -0,01% | OK |
| 2025-09 | receita_liquida | 11.387.959,79 | 11.364.136,19 | -0,21% | OK |
| 2025-09 | volume_liquido_t | 4.603,75 | 4.604,49 | 0,02% | OK |
| 2025-10 | receita_liquida | 12.828.308,06 | 12.826.334,24 | -0,02% | OK |
| 2025-10 | volume_liquido_t | 5.076,32 | 5.075,70 | -0,01% | OK |
| 2025-11 | receita_liquida | 12.409.640,04 | 12.409.377,69 | -0,00% | OK |
| 2025-11 | volume_liquido_t | 5.364,99 | 5.365,35 | 0,01% | OK |
| 2025-12 | receita_liquida | 11.491.890,94 | 11.490.192,83 | -0,01% | OK |
| 2025-12 | volume_liquido_t | 4.764,44 | 4.763,82 | -0,01% | OK |
| 2026-01 | receita_liquida | 12.359.225,64 | 12.348.520,48 | -0,09% | OK |
| 2026-01 | volume_liquido_t | 5.230,89 | 5.228,83 | -0,04% | OK |
| 2026-02 | receita_liquida | 10.615.170,08 | 10.613.758,22 | -0,01% | OK |
| 2026-02 | volume_liquido_t | 4.338,68 | 4.338,81 | 0,00% | OK |
| 2026-03 | receita_liquida | 12.164.395,57 | 12.173.806,99 | 0,08% | OK |
| 2026-03 | volume_liquido_t | 4.968,61 | 4.974,49 | 0,12% | OK |
| 2026-04 | receita_liquida | 11.558.305,96 | 11.554.253,67 | -0,04% | OK |
| 2026-04 | volume_liquido_t | 4.578,25 | 4.575,46 | -0,06% | OK |
| 2026-05 | receita_liquida | 11.472.626,57 | 11.464.380,03 | -0,07% | OK |
| 2026-05 | volume_liquido_t | 4.544,61 | 4.541,38 | -0,07% | OK |
| 2026-06 | receita_liquida | 12.369.060,12 | 12.378.176,06 | 0,07% | OK |
| 2026-06 | volume_liquido_t | 4.863,37 | 4.865,65 | 0,05% | OK |
| 2026-07 | receita_liquida | 9.721.819,75 | 9.718.360,77 | -0,04% | OK |
| 2026-07 | volume_liquido_t | 3.806,63 | 3.806,53 | -0,00% | OK |
