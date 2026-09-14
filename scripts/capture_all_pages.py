import os
import time
from playwright.sync_api import sync_playwright

os.makedirs("artifacts/prints_plataforma", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1600, "height": 1050},
        device_scale_factor=2
    )
    page = context.new_page()
    
    print("1. Acessando http://localhost:8501...")
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(2)
    
    # Login
    if page.locator("input[type='password']").count() > 0 or page.get_by_text("Senha").count() > 0:
        print("Efetuando login com Moinho2026@...")
        inputs = page.locator("input")
        if inputs.count() >= 2:
            inputs.nth(0).fill("admin")
            inputs.nth(1).fill("Moinho2026@")
            page.locator("button:has-text('Entrar')").click()
        time.sleep(4)
        page.wait_for_load_state("networkidle")
    
    print("Login concluído. Capturando Visão Geral...")
    time.sleep(3)
    page.screenshot(path="artifacts/prints_plataforma/01_cockpit_visao_geral.png")
    
    # Função para navegar no menu do Streamlit
    def navegar_para(texto_menu, nome_arquivo, wait_sec=5):
        print(f"\nNavegando para '{texto_menu}'...")
        try:
            # Tenta clicar no link da barra lateral
            sidebar_link = page.locator(f"[data-testid='stSidebarNav'] span:has-text('{texto_menu}')")
            if sidebar_link.count() > 0:
                sidebar_link.first.click()
            else:
                # Tentar texto genérico
                page.get_by_text(texto_menu, exact=False).first.click()
            time.sleep(wait_sec)
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            page.screenshot(path=f"artifacts/prints_plataforma/{nome_arquivo}.png")
            print(f"Salvo: {nome_arquivo}.png")
        except Exception as e:
            print(f"Erro ao navegar para {texto_menu}: {e}")

    # 1. Potencial de Mercado MG
    navegar_para("Potencial de Mercado MG", "02_potencial_mg_full", wait_sec=6)
    
    # 2. RCAs e Representantes
    navegar_para("RCAs", "03_rcas_full", wait_sec=5)

    # 3. Logística
    navegar_para("Logística", "04_logistica_full", wait_sec=5)

    # 4. Gestão de Mix
    navegar_para("Gestão de Mix", "05_gestao_mix_full", wait_sec=5)

    # 5. Clientes
    navegar_para("Clientes", "06_clientes_full", wait_sec=5)

    browser.close()

print("\nTodas as capturas finalizadas com sucesso!")
