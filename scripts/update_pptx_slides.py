import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt

sys.stdout.reconfigure(encoding='utf-8')

pptx_path = r"E:\HD_EXTERNO\Moinho\Dados\Dados_analise_diagnostico\2026-09 Alianzo ENTHUS - Proposta Consultoria Comercial - Moinho Sete Irmaos V4.pptx"

prs = Presentation(pptx_path)

print(f"Carregando apresentação: {len(prs.slides)} slides encontrados.")

# -------------------------------------------------------------------------------------------------
# 1. SLIDE 6: "MG Concentração" -> Inserir Mapa das 3 Camadas de Mercado de MG
# -------------------------------------------------------------------------------------------------
slide_6 = prs.slides[5]  # Slide 6 (índice 5)
img_mg = os.path.abspath("artifacts/prints_slides/01_potencial_mg_camadas.png")

if os.path.exists(img_mg):
    # Inserir imagem ocupando o centro/inferior do slide harmoniosamente
    left = Inches(0.56)
    top = Inches(1.80)
    width = Inches(12.2)
    height = Inches(4.85)
    slide_6.shapes.add_picture(img_mg, left, top, width, height)
    print("Slide 6: Imagem do Mapa das 3 Camadas de MG inserida com sucesso.")

notes_slide_6 = slide_6.notes_slide.notes_text_frame
notes_slide_6.text = (
    "NOTAS DO ORADOR — POTENCIAL DE MERCADO MG (3 CAMADAS):\n"
    "• Narrativa Executiva: Apresentar a tela 'Potencial de Mercado MG' da plataforma Visão Moinho como a prova visual do espaço de crescimento.\n"
    "• Como explicar o gráfico: A plataforma sobrepõe 3 camadas de dados reais: (1) Onde o Moinho já vende (apenas 121 dos 853 municípios); (2) Onde estão alocados os RCAs (cobertura concentrada no Triângulo); e (3) Onde está a demanda real de farinha estimada pelo cruzamento do cadastro do IBGE com o consumo padrão de padarias, indústrias e pizzarias.\n"
    "• Insight Chave: O vazio territorial é enorme — 8,16 milhões de mineiros e 1.753 t/mês de demanda mapeada onde o Moinho não vende uma única tonelada (com destaque para a Grande BH, que concentra 42% do espaço mapeado).\n"
    "• Potencial da Plataforma: Permite direcionar expansão de rotas e abertura de novos RCAs com precisão cirúrgica por município, evitando 'tiro no escuro'."
)

# -------------------------------------------------------------------------------------------------
# 2. SLIDE 18: "A base indireta (RCAs) não opera como um time" -> Inserir Scorecard / Dispersão de RCAs
# -------------------------------------------------------------------------------------------------
slide_18 = prs.slides[17]  # Slide 18 (índice 17)
# Vamos verificar se o slide 22 ou 18 é o melhor. No slide 22 ("Um padrão já existe dentro de casa"), há uma tabela vazia (Shape 9) onde o scorecard cai como uma luva!
# Vamos colocar no Slide 22 o scorecard dos representantes e no Slide 18 as notas correspondentes.

slide_22 = prs.slides[21]  # Slide 22 (índice 21)
img_rca = os.path.abspath("artifacts/prints_slides/03_rcas_quadrante.png")

if os.path.exists(img_rca):
    # No slide 22, remover ou cobrir a tabela vazia
    left = Inches(0.56)
    top = Inches(3.05)
    width = Inches(12.2)
    height = Inches(3.15)
    slide_22.shapes.add_picture(img_rca, left, top, width, height)
    print("Slide 22: Imagem do Scorecard e Performance de RCAs inserida com sucesso.")

notes_slide_22 = slide_22.notes_slide.notes_text_frame
notes_slide_22.text = (
    "NOTAS DO ORADOR — DESEMPENHO E BENCHMARK DE RCAs:\n"
    "• Narrativa Executiva: Mostrar que a solução não depende de inventar nada fora da empresa — o padrão de alta performance já existe dentro de casa.\n"
    "• Como explicar a tela: O painel da plataforma Visão Moinho cruza receita líquida, volume, PMV e margem proxy por vendedor. Destacar Leonel Soares (R$ 37,9 mi de faturamento com PMV de R$ 3.389/t — 29% acima da média da empresa) e Cláudio / CR Promoções (187 clientes ativos, 12 cidades e líder absoluto com 16,2% de toda a positivação da empresa).\n"
    "• Ponto de Impacto: Ambos operam sob a mesma tabela de preços, mesma política de frete e mesma marca de quem vende pouco e com desconto em outras regiões.\n"
    "• Potencial da Plataforma: O Visão Moinho monitora continuamente os desvios de PMV e positivação por representante, transformando boas práticas individuais em um playbook comercial escalável para toda a equipe."
)

# -------------------------------------------------------------------------------------------------
# 3. SLIDE 28: "O choque de gestão comercial" -> Inserir Cockpit Executivo da Plataforma Visão Moinho
# -------------------------------------------------------------------------------------------------
slide_28 = prs.slides[27]  # Slide 28 (índice 27)
img_cockpit = os.path.abspath("artifacts/prints_slides/00_cockpit_visao_geral.png")
if not os.path.exists(img_cockpit) or os.path.getsize(img_cockpit) < 100000:
    img_cockpit = os.path.abspath("artifacts/prints_plataforma/01_cockpit_visao_geral.png")

if os.path.exists(img_cockpit):
    left = Inches(0.56)
    top = Inches(1.65)
    width = Inches(12.2)
    height = Inches(4.15)
    slide_28.shapes.add_picture(img_cockpit, left, top, width, height)
    print("Slide 28: Imagem do Cockpit Geral da Plataforma inserida com sucesso.")

notes_slide_28 = slide_28.notes_slide.notes_text_frame
notes_slide_28.text = (
    "NOTAS DO ORADOR — PLATAFORMA VISÃO MOINHO COMO RADAR COMERCIAL:\n"
    "• Narrativa Executiva: Destacar que a plataforma já está desenvolvida, testada e em operação sobre os dados reais do Moinho.\n"
    "• Como explicar a tela: Apresentar o Cockpit Geral com os KPIs consolidados (R$ 518,36 mi de receita líquida, 198.790 t faturadas, margem proxy de 27,1%, 1.019 clientes ativos no último mês), evolução mensal de volume vs PMV e a decomposição do mix de produtos.\n"
    "• Proposta de Valor: A plataforma é o radar comercial da casa. Integrada ao ERP Sankhya, elimina a perda de tempo com planilhas manuais e discussões sobre 'qual número está certo'. As reuniões semanais passam a ser 100% orientadas à ação e estratégia.\n"
    "• Ganho para a Diretoria: Visibilidade em tempo real sobre clientes em risco, perda de margem, rotas de frete caras e gaps de cobertura."
)

# -------------------------------------------------------------------------------------------------
# 4. SLIDE 4: "Os ativos são reais e estão em operação" -> Inserir Notas do Orador com a Auditoria
# -------------------------------------------------------------------------------------------------
slide_4 = prs.slides[3]  # Slide 4 (índice 3)
notes_slide_4 = slide_4.notes_slide.notes_text_frame
notes_slide_4.text = (
    "NOTAS DO ORADOR — AUDITORIA E VALIDAÇÃO DOS NÚMEROS (SEGURANÇA TOTAL):\n"
    "• Roteiro de Apoio: Caso a diretoria questione qualquer número deste slide, todos os dados foram 100% auditados e reconciliados no DW analítico (PostgreSQL):\n"
    "  1. Receita Líquida: R$ 518,36 mi (R$ 525,54 mi vendas brutas − R$ 7,19 mi devoluções).\n"
    "  2. Volume Líquido: 198.790 t (201.103 t brutas − 2.313 t devolvidas).\n"
    "  3. Margem Proxy: 27,1% calculada sobre o Custo Gerencial CUSGER (R$ 139,97 mi de margem).\n"
    "  4. Clientes Ativos no Último Mês: 1.019 clientes compradores em Julho/2026.\n"
    "  5. PMVs de Portfólio (sem bonificação): Farinhas R$ 2.947/t · Bolo R$ 6.522/t · Misturas R$ 2.642/t · Farelo R$ 1.128/t.\n"
    "  6. Mix de Bolo: 3,8% do volume e 9,4% da receita.\n"
    "  7. Base Viva: 2.230 novos clientes e 559 reativações (após ≥6 meses sem comprar), com média de 876 ativos/mês.\n"
    "  8. Queda de Devoluções: de 103,7 t para 34,8-37,1 t em 2026 (queda de ~66% em toneladas e 77,8% em valor).\n"
    "  9. Leonel Soares: R$ 37,9 mi com PMV de R$ 3.389/t (+28,9% vs média da empresa de R$ 2.629/t).\n"
    "  10. Cláudio (CR Promoções / codvend 29): 187 clientes em 2026, 12 cidades, 16,2% da positivação da empresa."
)

prs.save(pptx_path)
print(f"\nArquivo PPTX atualizado e salvo com sucesso em:\n{pptx_path}")
