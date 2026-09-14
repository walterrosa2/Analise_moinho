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
    
    # 1. Login inicial
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(1)
    if page.locator("input[type='password']").count() > 0:
        inputs = page.locator("input")
        if inputs.count() >= 2:
            inputs.nth(0).fill("admin")
            inputs.nth(1).fill("Moinho2026@")
            page.locator("button:has-text('Entrar')").click()
        time.sleep(3)
        page.wait_for_load_state("networkidle")

    def capturar_url(path, filename, wait_s=4):
        print(f"Acessando http://localhost:8501/{path}...")
        page.goto(f"http://localhost:8501/{path}", wait_until="networkidle")
        time.sleep(wait_s)
        # Recolher sidebar
        try:
            collapse_btn = page.locator("button[data-testid='stSidebarCollapseButton']")
            if collapse_btn.count() > 0 and collapse_btn.is_visible():
                collapse_btn.click()
                time.sleep(1)
        except Exception:
            pass
        time.sleep(1)
        # Salvar screenshot
        main_view = page.locator("section[data-testid='stMain']")
        if main_view.count() > 0:
            main_view.screenshot(path=f"artifacts/prints_slides/{filename}.png")
        else:
            page.screenshot(path=f"artifacts/prints_slides/{filename}.png")
        print(f"Salvo: {filename}.png")

    capturar_url("p00_visao_geral", "00_cockpit_visao_geral", wait_s=4)
    capturar_url("p13_potencial_mg", "01_potencial_mg_mapas", wait_s=6)
    capturar_url("p05_rcas", "02_rcas_scorecard", wait_s=4)
    capturar_url("p09_logistica", "03_logistica_frete", wait_s=4)

    browser.close()

print("Capturas concluídas via URL direta!")
