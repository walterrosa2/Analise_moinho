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

        titles = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll(".gtitle")).map(el => ({
                text: el.textContent,
                html: el.outerHTML,
                unformatted: el.getAttribute("data-unformatted")
            }));
        }''')
        print("GTITLES:", titles)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
