import os
import time
from playwright.sync_api import sync_playwright

os.makedirs("artifacts/prints_slides", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=2
    )
    page = context.new_page()
    
    print("Acessando Streamlit...")
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(2)
    
    # Login
    if page.locator("input[type='password']").count() > 0 or page.get_by_text("Senha").count() > 0:
        inputs = page.locator("input")
        if inputs.count() >= 2:
            inputs.nth(0).fill("admin")
            inputs.nth(1).fill("Moinho2026@")
            page.locator("button:has-text('Entrar')").click()
        time.sleep(3)
        page.wait_for_load_state("networkidle")
    
    # Função para recolher sidebar se estiver aberta
    def recolher_sidebar():
        try:
            collapse_btn = page.locator("button[data-testid='stSidebarCollapseButton']")
            if collapse_btn.count() > 0 and collapse_btn.is_visible():
                collapse_btn.click()
                time.sleep(1)
        except Exception:
            pass

    # 1. CAPTURA: Potencial de Mercado MG (Mapa das 3 Camadas)
    print("Navegando para Potencial de Mercado MG...")
    page.locator("[data-testid='stSidebarNav'] span:has-text('Potencial de Mercado MG')").click()
    time.sleep(5)
    page.wait_for_load_state("networkidle")
    recolher_sidebar()
    time.sleep(2)
    
    # Screenshot da área principal
    main_view = page.locator("section[data-testid='stMain']")
    if main_view.count() > 0:
        main_view.screenshot(path="artifacts/prints_slides/01_potencial_mg_camadas.png")
    else:
        page.screenshot(path="artifacts/prints_slides/01_potencial_mg_camadas.png")
    print("Salvo: 01_potencial_mg_camadas.png")

    # 2. CAPTURA: Potencial de Mercado MG - Aba White Space
    print("Clicando na aba 'Sobreposição · White Space'...")
    try:
        page.get_by_text("Sobreposição · White Space").click()
        time.sleep(4)
        page.wait_for_load_state("networkidle")
        if main_view.count() > 0:
            main_view.screenshot(path="artifacts/prints_slides/02_potencial_mg_whitespace.png")
        print("Salvo: 02_potencial_mg_whitespace.png")
    except Exception as e:
        print(f"Erro na aba White Space: {e}")

    # Abrir sidebar para trocar de página
    try:
        page.locator("button[data-testid='stSidebarCollapseButton']").click()
        time.sleep(1)
    except Exception:
        pass

    # 3. CAPTURA: RCAs e Representantes (Dispersão e Scorecard)
    print("Navegando para RCAs...")
    page.locator("[data-testid='stSidebarNav'] span:has-text('RCAs')").click()
    time.sleep(4)
    page.wait_for_load_state("networkidle")
    
    # Clicar na aba Quadrante se existir
    try:
        page.get_by_text("Quadrante").click()
        time.sleep(2)
    except Exception:
        pass
    recolher_sidebar()
    time.sleep(2)
    if main_view.count() > 0:
        main_view.screenshot(path="artifacts/prints_slides/03_rcas_quadrante.png")
    print("Salvo: 03_rcas_quadrante.png")

    # Reabrir sidebar
    try:
        page.locator("button[data-testid='stSidebarCollapseButton']").click()
        time.sleep(1)
    except Exception:
        pass

    # 4. CAPTURA: Logística e Frete
    print("Navegando para Logística...")
    page.locator("[data-testid='stSidebarNav'] span:has-text('Logística')").click()
    time.sleep(4)
    page.wait_for_load_state("networkidle")
    recolher_sidebar()
    time.sleep(2)
    if main_view.count() > 0:
        main_view.screenshot(path="artifacts/prints_slides/04_logistica_frete.png")
    print("Salvo: 04_logistica_frete.png")

    # Reabrir sidebar
    try:
        page.locator("button[data-testid='stSidebarCollapseButton']").click()
        time.sleep(1)
    except Exception:
        pass

    # 5. CAPTURA: Cockpit Geral (Visão Geral)
    print("Navegando para Visão Geral...")
    page.locator("[data-testid='stSidebarNav'] span:has-text('Visão Geral')").click()
    time.sleep(4)
    page.wait_for_load_state("networkidle")
    recolher_sidebar()
    time.sleep(2)
    if main_view.count() > 0:
        main_view.screenshot(path="artifacts/prints_slides/05_cockpit_visao_geral.png")
    print("Salvo: 05_cockpit_visao_geral.png")

    browser.close()

print("\nTodas as capturas dos slides foram geradas com sucesso!")
