import asyncio
import re
from playwright.async_api import async_playwright

async def scan_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})
        await page.goto("http://localhost:8501", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Login
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
        await page.wait_for_timeout(2000)
        
        # Testar texto em nós SVG em p00
        svg_texts = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('text')).map(t => t.textContent || '');
        }''')
        svg_undef = [t for t in svg_texts if 'undefined' in t.lower()]
        print(f"P00 SVG undefined texts: {len(svg_undef)}")

        # Varrer todas as páginas da barra lateral
        links = await page.query_selector_all('a[data-testid="stSidebarNavLink"]')
        print(f"Total sidebar links: {len(links)}")
        
        total_found = len(svg_undef)
        for idx in range(len(links)):
            # Recapturar links pois o DOM pode atualizar
            cur_links = await page.query_selector_all('a[data-testid="stSidebarNavLink"]')
            link = cur_links[idx]
            link_href = await link.get_attribute("href")
            link_name = (await link.text_content() or "").encode("ascii", "ignore").decode("ascii").strip()
            
            print(f"\n--- Checking Page [{idx}]: {link_name} ({link_href}) ---")
            await link.click()
            await page.wait_for_timeout(3500)
            
            # Checar todos os textos SVG
            page_svg_texts = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('text')).map(t => t.textContent || '');
            }''')
            page_svg_undef = [t for t in page_svg_texts if 'undefined' in t.lower()]
            
            # Checar todo o DOM visível
            body_text = await page.evaluate('() => document.body.innerText')
            body_undef = list(re.finditer(r'\bundefined\b', body_text, re.IGNORECASE))
            
            if page_svg_undef or body_undef:
                print(f"  [ALERTA] Encontrado undefined na pagina {link_name}!")
                print(f"    SVG undef: {page_svg_undef}")
                print(f"    Body undef count: {len(body_undef)}")
                total_found += len(page_svg_undef) + len(body_undef)
            else:
                print(f"  [OK] Pagina {link_name} 100% LIMPA (0 undefined).")

        print(f"\n==========================================")
        print(f"TOTAL DE OCORRENCIAS DE UNDEFINED EM TODA A PLATAFORMA: {total_found}")
        print(f"==========================================")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scan_all())
