import os
import time
from playwright.sync_api import sync_playwright

os.makedirs("artifacts/prints_plataforma", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        device_scale_factor=2  # Super nitidez
    )
    page = context.new_page()
    
    print("1. Acessando http://localhost:8501...")
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(2)
    
    # Se houver tela de login
    if page.locator("input[type='password']").count() > 0 or page.get_by_text("Senha").count() > 0:
        print("Tela de login detectada. Efetuando login...")
        inputs = page.locator("input")
        # Se tiver usuario e senha
        if inputs.count() >= 2:
            inputs.nth(0).fill("admin")
            inputs.nth(1).fill("admin")
            page.keyboard.press("Enter")
        elif inputs.count() == 1:
            inputs.nth(0).fill("admin")
            page.keyboard.press("Enter")
        time.sleep(3)
        page.wait_for_load_state("networkidle")
    
    print("Página inicial carregada!")
    time.sleep(3)
    page.screenshot(path="artifacts/prints_plataforma/01_visao_geral.png")
    
    # 2. Navegar para Potencial de Mercado MG
    print("2. Navegando para Potencial de Mercado MG...")
    try:
        # Clicar no menu lateral
        link_potencial = page.get_by_text("Potencial de Mercado MG", exact=False)
        if link_potencial.count() > 0:
            link_potencial.first.click()
            time.sleep(5)
            page.wait_for_load_state("networkidle")
            page.screenshot(path="artifacts/prints_plataforma/02_potencial_mg_full.png")
            print("Potencial MG capturado!")
    except Exception as e:
        print(f"Erro ao navegar para Potencial MG: {e}")
        
    # 3. Navegar para RCAs
    print("3. Navegando para RCAs e Representantes...")
    try:
        link_rcas = page.get_by_text("RCAs e Representantes", exact=False)
        if link_rcas.count() == 0:
            link_rcas = page.get_by_text("RCAs", exact=False)
        if link_rcas.count() > 0:
            link_rcas.first.click()
            time.sleep(4)
            page.wait_for_load_state("networkidle")
            page.screenshot(path="artifacts/prints_plataforma/03_rcas_full.png")
            print("RCAs capturado!")
    except Exception as e:
        print(f"Erro ao navegar para RCAs: {e}")

    # 4. Navegar para Logística
    print("4. Navegando para Logística...")
    try:
        link_log = page.get_by_text("Logística", exact=False)
        if link_log.count() > 0:
            link_log.first.click()
            time.sleep(4)
            page.wait_for_load_state("networkidle")
            page.screenshot(path="artifacts/prints_plataforma/04_logistica_full.png")
            print("Logística capturado!")
    except Exception as e:
        print(f"Erro ao navegar para Logística: {e}")

    # 5. Navegar para Gestão de Mix / Produtos
    print("5. Navegando para Gestão de Mix...")
    try:
        link_mix = page.get_by_text("Gestão de Mix", exact=False)
        if link_mix.count() > 0:
            link_mix.first.click()
            time.sleep(4)
            page.wait_for_load_state("networkidle")
            page.screenshot(path="artifacts/prints_plataforma/05_mix_full.png")
            print("Mix capturado!")
    except Exception as e:
        print(f"Erro ao navegar para Mix: {e}")

    browser.close()

print("Capturas concluídas!")
