import os
import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        device_scale_factor=2
    )
    page = context.new_page()
    
    print("Acessando Streamlit...")
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(2)
    
    # Login
    if page.locator("input[type='password']").count() > 0:
        inputs = page.locator("input")
        if inputs.count() >= 2:
            inputs.nth(0).fill("admin")
            inputs.nth(1).fill("Moinho2026@")
            page.locator("button:has-text('Entrar')").click()
        time.sleep(3)
        page.wait_for_load_state("networkidle")
    
    time.sleep(2)
    page.screenshot(path="artifacts/valida_logo_sidebar.png")
    print("Screenshot salvo em artifacts/valida_logo_sidebar.png")
    browser.close()
