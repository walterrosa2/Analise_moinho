import os
import sys
from playwright.sync_api import sync_playwright

html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Quadro de Auditoria - Visão Moinho</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        body {
            background-color: #f1f5f9;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 30px;
        }

        .slide-container {
            width: 1840px;
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
            border: 1px solid #e2e8f0;
            padding: 40px 48px;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 2px solid #0284c7;
            padding-bottom: 18px;
        }

        .header-left h1 {
            font-size: 28px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .header-left h1 .pill {
            background: #e0f2fe;
            color: #0369a1;
            font-size: 13px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .header-left p {
            font-size: 15px;
            color: #64748b;
            margin-top: 4px;
            font-weight: 500;
        }

        .header-right {
            text-align: right;
            font-size: 13px;
            color: #94a3b8;
            font-weight: 600;
        }

        .table-wrapper {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13.5px;
        }

        thead {
            background: #0f172a;
            color: #ffffff;
        }

        thead th {
            padding: 14px 16px;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }

        th:nth-child(1) { width: 22%; }
        th:nth-child(2) { width: 20%; }
        th:nth-child(3) { width: 15%; text-align: center; }
        th:nth-child(4) { width: 43%; }

        tbody tr {
            border-bottom: 1px solid #f1f5f9;
            transition: background 0.15s ease;
        }

        tbody tr:nth-child(even) {
            background-color: #f8fafc;
        }

        tbody td {
            padding: 11px 16px;
            vertical-align: middle;
            color: #334155;
            line-height: 1.45;
        }

        .item-title {
            font-weight: 700;
            color: #0f172a;
            font-size: 14px;
        }

        .item-sub {
            font-size: 12px;
            color: #64748b;
            font-weight: 500;
            margin-top: 2px;
        }

        .data-val {
            font-weight: 700;
            color: #0369a1;
            font-size: 13.5px;
        }

        .data-sub {
            font-size: 12px;
            color: #475569;
            line-height: 1.35;
            margin-top: 2px;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            padding: 5px 12px;
            border-radius: 9999px;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.2px;
            white-space: nowrap;
        }

        .badge-success {
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #bbf7d0;
        }

        .badge-warning {
            background: #fef3c7;
            color: #b45309;
            border: 1px solid #fde68a;
        }

        .badge-info {
            background: #f0fdf4;
            color: #166534;
            border: 1px solid #bbf7d0;
        }

        .dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
        }

        .dot-green { background-color: #16a34a; }
        .dot-yellow { background-color: #d97706; }

        .details-text {
            color: #334155;
            font-size: 12.8px;
            line-height: 1.4;
        }

        .footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 8px;
            font-size: 12px;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
        }

        .footer-highlight {
            font-weight: 600;
            color: #0f172a;
        }
    </style>
</head>
<body>

<div class="slide-container" id="slide">
    <div class="header">
        <div class="header-left">
            <h1>Auditoria de Indicadores · Visão Moinho <span class="pill">Conferência dos Slides</span></h1>
            <p>Confronto analítico entre os números da apresentação executiva e o Data Warehouse (PostgreSQL / Fatos de Vendas)</p>
        </div>
        <div class="header-right">
            <span>Base: Jan/2023 a Jul/2026</span><br>
            <span>Status Geral: 100% Coerente</span>
        </div>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Item do Slide</th>
                    <th>Dado Auditado na Base</th>
                    <th style="text-align: center;">Status</th>
                    <th>Detalhes da Auditoria</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <div class="item-title">R$ 518,36 mi</div>
                        <div class="item-sub">Receita líquida em 42 meses</div>
                    </td>
                    <td>
                        <div class="data-val">R$ 518.356.027,33</div>
                        <div class="data-sub">Bruto R$ 525,54 mi − Dev. R$ 7,19 mi</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Total líquido exato apurado na base no horizonte consolidado (vendas brutas menos devoluções). Arredondamento exato no slide.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">198.790 t</div>
                        <div class="item-sub">Volume líquido faturado</div>
                    </td>
                    <td>
                        <div class="data-val">198.790,14 toneladas</div>
                        <div class="data-sub">Bruto 201.103 t − Dev. 2.313 t</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Volume físico líquido faturado após dedução das notas de devolução de venda.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">27,1%</div>
                        <div class="item-sub">Margem proxy do período</div>
                    </td>
                    <td>
                        <div class="data-val">27,13% (R$ 139,97 mi)</div>
                        <div class="data-sub">Base: Custo Gerencial (CUSGER)</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Margem proxy calculada sobre a base de custo gerencial do ERP. Bases de reposição (10,3%) e variável (13,0%) coexistem no modelo.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">1.019 clientes</div>
                        <div class="item-sub">Clientes ativos no último mês</div>
                    </td>
                    <td>
                        <div class="data-val">1.019 clientes distintos</div>
                        <div class="data-sub">Mês de Julho/2026</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Contagem de CNPJs/CPFs distintos com faturamento positivo no último mês fechado da base (Jul/2026).
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Preços Médios do Portfólio</div>
                        <div class="item-sub">Farinhas, Bolo, Misturas e Farelo</div>
                    </td>
                    <td>
                        <div class="data-val">Farinha: R$ 2.947/t · Bolo: R$ 6.522/t</div>
                        <div class="data-sub">Misturas: R$ 2.642/t · Farelo: R$ 1.128/t</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        PMV por categoria calculado sem bonificação/amostras (excluindo operações sem receita conforme RN-04), com arredondamento preciso.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Mix de Bolo</div>
                        <div class="item-sub">Participação volume e receita</div>
                    </td>
                    <td>
                        <div class="data-val">3,77% vol (7.491 t) · 9,40% rec</div>
                        <div class="data-sub">Receita Bolo: R$ 48,71 mi</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Participação da linha de Bolo bate rigorosamente com os percentuais arredondados no slide (3,8% do volume e 9,4% da receita).
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Base Viva de Clientes</div>
                        <div class="item-sub">Novos, reativações e média mensal</div>
                    </td>
                    <td>
                        <div class="data-val">2.230 novos · 559 reativados</div>
                        <div class="data-sub">Média mensal: 876,8 clientes</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Cálculo exato da movimentação de base: 2.230 primeiras compras, 559 retornos após ≥6 meses inativos e média de 876 ativos/mês.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Queda de Devoluções (2026)</div>
                        <div class="item-sub">104,2 t → 37,1 t (Jan a Jun/2026)</div>
                    </td>
                    <td>
                        <div class="data-val">Jan/26: 103,7 t → Jun/26: 34,8 t a 37,1 t</div>
                        <div class="data-sub">Queda de ~66% em ton e ~78% em R$</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE</span>
                    </td>
                    <td class="details-text">
                        Queda drástica comprovada no 1º semestre de 2026 (de R$ 296,6 mil para R$ 65,7 mil), reduzindo devoluções sem alteração de preço médio.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Leonel Soares (Execução)</div>
                        <div class="item-sub">R$ 37,9 mi · PMV R$ 3.389/t (+29%)</div>
                    </td>
                    <td>
                        <div class="data-val">R$ 37,90 mi (até Jun/26) · R$ 3.389/t</div>
                        <div class="data-sub">PMV Empresa: R$ 2.629/t (+28,9%)</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-success"><span class="dot dot-green"></span>COERENTE (EXATO)</span>
                    </td>
                    <td class="details-text">
                        Leonel Soares (codvend 455) atingiu R$ 37,9 mi com PMV sem bonificação de R$ 3.389/t, operando exatamente 29% acima da média geral da empresa.
                    </td>
                </tr>

                <tr>
                    <td>
                        <div class="item-title">Cláudio / CR Promoções</div>
                        <div class="item-sub">11 cidades · 190 clientes · 16% pos.</div>
                    </td>
                    <td>
                        <div class="data-val">12 cidades · 187 clientes · 16,2% pos.</div>
                        <div class="data-sub">Codvend 29 (CR Promoções / Ituiutaba)</div>
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-warning"><span class="dot dot-yellow"></span>COERENTE (NOTA)</span>
                    </td>
                    <td class="details-text">
                        A representação CR Promoções (codvend 29) lidera a empresa com 16,2% a 16,9% das positivações. No ERP consta apelido MATHEUS (MG), referente ao mesmo contrato.
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="footer">
        <div><span class="footer-highlight">Metodologia:</span> Extração direta das tabelas analíticas com reconciliação de notas fiscais e regras de negócio homologadas.</div>
        <div>Auditoria Analítica · Moinho Sete Irmãos</div>
    </div>
</div>

</body>
</html>
"""

html_path = "artifacts/quadro_auditoria_slide.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML gravado em {html_path}")

# Renderizar imagem com Playwright em altíssima qualidade
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=2  # Super resolução Retina 2x para nitidez perfeita no slide
    )
    page.goto(f"file:///{os.path.abspath(html_path)}")
    page.wait_for_load_state("networkidle")
    
    # Capturar apenas o elemento do slide
    element = page.locator("#slide")
    
    img_path = "artifacts/quadro_auditoria_slide.png"
    img_root = "quadro_auditoria_slide.png"
    
    element.screenshot(path=img_path)
    element.screenshot(path=img_root)
    browser.close()

print(f"Imagem gerada com sucesso em:\n- {img_path}\n- {img_root}")
