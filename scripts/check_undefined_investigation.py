import asyncio
import re
from playwright.async_api import async_playwright

async def investigate():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})
        await page.goto("http://localhost:8501", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Verificar se está na tela de login
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

        # Checar página inicial
        await page.wait_for_timeout(3000)

        # Listar gráficos
        plots = await page.query_selector_all(".js-plotly-plot")
        print(f"Total plotly plots found: {len(plots)}")

        for i, plot in enumerate(plots):
            box = await plot.bounding_box()
            if not box:
                continue
            # Vamos testar passar o mouse em vários pontos horizontais do gráfico
            for step in range(1, 10):
                x_pos = box["x"] + (box["width"] * step / 10.0)
                y_pos = box["y"] + (box["height"] * 0.5)
                await page.mouse.move(x_pos, y_pos)
                await page.wait_for_timeout(100)
                
                # Coletar todo texto dentro do plot via evaluate
                texts = await page.evaluate('''() => {
                    const el = document.querySelectorAll(".js-plotly-plot")[%d];
                    if (!el) return [];
                    return Array.from(el.querySelectorAll("text")).map(t => t.textContent || "");
                }''' % i)
                
                for val in texts:
                    if "undefined" in val.lower():
                        print(f"FOUND 'undefined' in Plot {i} (step {step}): text='{val}'")

        # Inspecionar todo o DOM
        content = await page.content()
        matches = list(re.finditer(r"undefined", content, re.IGNORECASE))
        print(f"Total occurrences of 'undefined' in DOM HTML: {len(matches)}")
        for m in matches:
            start = max(0, m.start() - 80)
            end = min(len(content), m.end() + 80)
            print("--- HTML SNIPPET ---")
            print(content[start:end].replace("\n", " "))

        # Agora vamos navegar por outras páginas da barra lateral e testar
        links = await page.query_selector_all('a[data-testid="stSidebarNavLink"]')
        print(f"Total sidebar links: {len(links)}")
        for idx, link in enumerate(links):
            link_text = (await link.text_content() or "").strip()
            print(f"\nTesting page [{idx}]: {link_text}")
            await link.click()
            await page.wait_for_timeout(3000)
            
            page_content = await page.content()
            p_matches = list(re.finditer(r"undefined", page_content, re.IGNORECASE))
            if p_matches:
                print(f"  --> Page '{link_text}' has {len(p_matches)} occurrences of 'undefined'!")
                for pm in p_matches:
                    st = max(0, pm.start() - 60)
                    en = min(len(page_content), pm.end() + 60)
                    print(f"      Snippet: {page_content[st:en].replace(chr(10), ' ')}")
            else:
                print(f"  --> Page '{link_text}' clean (0 'undefined').")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(investigate())
