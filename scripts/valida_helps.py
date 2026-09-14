import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})
        await page.goto("http://localhost:8501", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        pwd = await page.query_selector('input[type="password"]')
        if pwd:
            inputs = await page.query_selector_all('input')
            if len(inputs) >= 2:
                await inputs[0].fill("admin")
                await inputs[1].fill("Moinho2026@")
                btn = await page.query_selector('button[kind="primary"]')
                if btn:
                    await btn.click()
                else:
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(4000)

        # Capturar tela de Visao Geral com os novos tooltips
        await page.screenshot(path="artifacts/valida_helps_p00.png", full_page=True)

        # Navegar para Potencial MG
        links = await page.query_selector_all('a[data-testid="stSidebarNavLink"]')
        for l in links:
            txt = await l.text_content()
            if txt and "Potencial" in txt:
                await l.click()
                await page.wait_for_timeout(3500)
                await page.screenshot(path="artifacts/valida_helps_p13.png", full_page=True)
                break

        print("Evidencias capturadas com sucesso!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
