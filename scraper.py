"""
TikTok Comments Scraper using Playwright - Contorna WAF com navegador real
Suporte a múltiplas URLs e extração robusta de comentários.
"""
import asyncio
import json
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper de comentários do TikTok usando Playwright."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}

    async def _setup_browser(self):
        """Configura o navegador com headers realistas e anti-detecção."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='pt-BR',
        )

        # Anti-detecção de automação
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            // Remove webdriver property from navigator
            delete navigator.__proto__.webdriver;
        """)

        return playwright, browser, context

    async def _wait_for_comments(self, page):
        """Aguarda os comentários carregarem na página."""
        selectors_to_try = [
            '[data-e2e="comment-list"]',
            '[class*="comment-list"]',
            '[class*="comments"]',
        ]

        for selector in selectors_to_try:
            try:
                await page.wait_for_selector(selector, timeout=15000)
                console.print(f"[green]✓[/green] Comentários encontrados via '{selector}'")
                return True
            except PlaywrightTimeout:
                continue

        console.print("[yellow]⚠[/yellow] Nenhum seletor de comentários encontrado")
        return False

    async def _scroll_comments(self, page):
        """Rola a página para carregar mais comentários via lazy loading."""
        max_scrolls = 20
        no_change_count = 0

        for i in range(max_scrolls):
            await asyncio.sleep(random.uniform(1.5, 3))

            try:
                # Tenta encontrar o container de comentários
                comment_container = page.locator('[data-e2e="comment-list"]').first
                if not await comment_container.count():
                    break

                last_height = await comment_container.evaluate('el => el.scrollHeight')

                # Rola para baixo em incrementos
                for _ in range(3):
                    await comment_container.evaluate('el => el.scrollTop += 600')
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                new_height = await comment_container.evaluate('el => el.scrollHeight')

                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        console.print("[green]✓[/green] Não há mais comentários para carregar")
                        return True
                else:
                    no_change_count = 0
                    console.print(f"[blue]↻[/blue] Scroll {i+1}: carregando mais...")

            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Erro ao rolar (scroll {i}): {e}")
                break

        return True

    async def _extract_comments(self, page):
        """Extrai os comentários do DOM via JavaScript no navegador."""
        comments_data = []

        try:
            raw_comments = await page.evaluate("""
                () => {
                    const comments = [];

                    // Tenta múltiplos seletores para encontrar os comentários
                    let commentElements;
                    if (document.querySelectorAll('[data-e2e="comment-list"] .comment-item').length > 0) {
                        commentElements = document.querySelectorAll('[data-e2e="comment-list"] .comment-item');
                    } else if (document.querySelectorAll('[class*="comment-list"] [class*="item"]').length > 0) {
                        commentElements = document.querySelectorAll('[class*="comment-list"] [class*="item"]');
                    } else {
                        // Fallback: tenta encontrar qualquer elemento com texto de comentário
                        const allSpans = document.querySelectorAll('span, p, div');
                        return []; // Não encontrou estrutura conhecida
                    }

                    commentElements.forEach(el => {
                        try {
                            // Extrai texto do comentário
                            let textEl = el.querySelector(
                                '[data-e2e="comment-text"], [class*="comment-text"], ' +
                                '.text, p, span'
                            );
                            let text = '';
                            if (textEl) text = textEl.textContent?.trim() || '';

                            // Extrai likes do comentário
                            let likeEl = el.querySelector(
                                '[data-e2e="like-count"], [class*="like"], .count, ' +
                                '[class*="likes"]'
                            );
                            let likes = 0;
                            if (likeEl) {
                                const likeText = likeEl.textContent?.trim() || '0';
                                const numMatch = likeText.match(/([\d.]+)([KMkm]?)?/);
                                if (numMatch) {
                                    let num = parseFloat(numMatch[1]);
                                    const suffix = numMatch[2]?.toUpperCase();
                                    if (suffix === 'K') num *= 1000;
                                    else if (suffix === 'M') num *= 1000000;
                                    likes = Math.round(num);
                                }
                            }

                            // Extrai número de respostas
                            let replyEl = el.querySelector(
                                '[data-e2e="reply-count"], [class*="reply"]'
                            );
                            let replies = 0;
                            if (replyEl) {
                                const replyText = replyEl.textContent?.trim() || '0';
                                const replyMatch = replyText.match(/([\d.]+)([KMkm]?)?/);
                                if (replyMatch) {
                                    let num = parseFloat(replyMatch[1]);
                                    const suffix = replyMatch[2]?.toUpperCase();
                                    if (suffix === 'K') num *= 1000;
                                    else if (suffix === 'M') num *= 1000000;
                                    replies = Math.round(num);
                                }
                            }

                            // Extrai autor
                            let authorEl = el.querySelector(
                                '[data-e2e="comment-author"], [class*="author"], .username'
                            );
                            let author = '';
                            if (authorEl) author = authorEl.textContent?.trim() || '';

                            // Extrai data
                            let dateEl = el.querySelector(
                                '[data-e2e="comment-time"], [class*="time"]'
                            );
                            let date = '';
                            if (dateEl) date = dateEl.textContent?.trim() || '';

                            if (text && text.length > 0) {
                                comments.push({
                                    text: text,
                                    likes: likes,
                                    replies_count: replies,
                                    author: author,
                                    date: date,
                                });
                            }
                        } catch(e) {}
                    });

                    return comments;
                }
            """)

            if raw_comments:
                console.print(f"[green]✓[/green] {len(raw_comments)} comentários extraídos")
                comments_data.extend(raw_comments)
            else:
                # Fallback: tenta extrair texto de qualquer elemento visível na área de comentários
                console.print("[yellow]⚠[/yellow] Nenhum comentário encontrado com seletor padrão, tentando fallback...")
                fallback = await page.evaluate("""
                    () => {
                        const results = [];
                        // Tenta encontrar textos em elementos dentro do container principal
                        const allTexts = document.querySelectorAll('[data-e2e="comment-list"]');
                        if (allTexts.length > 0) {
                            allTexts.forEach(el => {
                                const textNodes = el.querySelectorAll('span, p, div');
                                textNodes.forEach(node => {
                                    const t = node.textContent?.trim();
                                    if (t && t.length > 3 && t.length < 500) {
                                        results.push({text: t, likes: 0, replies_count: 0, author: '', date: ''});
                                    }
                                });
                            });
                        }
                        return results;
                    }
                """)
                if fallback:
                    console.print(f"[green]✓[/green] {len(fallback)} comentários extraídos (fallback)")
                    comments_data.extend(fallback)

        except Exception as e:
            console.print(f"[red]✗[/red] Erro ao extrair comentários: {e}")

        return comments_data

    async def _extract_video_info(self, page):
        """Extrai informações do vídeo (likes, shares, descrição)."""
        try:
            video_data = await page.evaluate("""
                () => {
                    const info = {};

                    // Likes do vídeo
                    const likeBtn = document.querySelector('[data-e2e="like-button"]');
                    if (likeBtn) {
                        const countEl = likeBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.likes = countEl.textContent?.trim() || '';
                    }

                    // Comentários do vídeo
                    const commentBtn = document.querySelector('[data-e2e="comment-button"]');
                    if (commentBtn) {
                        const countEl = commentBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.comment_count = countEl.textContent?.trim() || '';
                    }

                    // Shares do vídeo
                    const shareBtn = document.querySelector('[data-e2e="share-button"]');
                    if (shareBtn) {
                        const countEl = shareBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.shares = countEl.textContent?.trim() || '';
                    }

                    // Descrição do vídeo
                    const descEl = document.querySelector(
                        '[data-e2e="video-desc"], .desc, [class*="description"]'
                    );
                    if (descEl) info.description = descEl.textContent?.trim() || '';

                    return info;
                }
            """)
            self.video_info = video_data
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao extrair info do vídeo: {e}")

    async def scrape(self, url):
        """Realiza o scraping completo de um vídeo TikTok."""
        playwright = None
        browser = None

        with console.status(f"🌐 Acessando: {url}", spinner="dots") as status:
            try:
                # Setup navegador
                playwright, browser, context = await self._setup_browser()
                page = await context.new_page()

                # Acessa a URL
                response = await page.goto(url, wait_until='networkidle', timeout=60000)

                if not response.ok:
                    console.print(f"[red]✗[/red] Erro HTTP {response.status} ao carregar página")
                    return [], {}

                # Aguarda carregamento inicial
                await asyncio.sleep(5)

                # Tenta clicar no botão de comentários se necessário
                try:
                    comment_btn = page.locator('[data-e2e="comment-button"]')
                    if await comment_btn.count() > 0:
                        console.print("[blue]💬[/blue] Abrindo seção de comentários...")
                        await comment_btn.click()
                        await asyncio.sleep(3)
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Não foi possível clicar no botão: {e}")

                # Aguarda comentários carregarem
                if not await self._wait_for_comments(page):
                    return [], {}

                # Extrai info do vídeo
                await self._extract_video_info(page)

                # Rola para carregar mais comentários
                console.print("[blue]⬇️[/blue] Rolando para carregar mais comentários...")
                await self._scroll_comments(page)

                # Aguarda mais um pouco após o último scroll
                await asyncio.sleep(2)

                # Extrai os comentários
                self.comments = await self._extract_comments(page)

            except Exception as e:
                console.print(f"[red]✗[/red] Erro durante o scraping: {e}")
                import traceback
                console.print(traceback.format_exc())

            finally:
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

        return self.comments, self.video_info


async def scrape_single_url(url):
    """Scrapes uma única URL e retorna os resultados."""
    scraper = TikTokScraper(headless=True)
    comments, video_info = await scraper.scrape(url)
    return {
        'url': url,
        'comments': comments or [],
        'video_info': video_info or {},
        'success': len(comments) > 0,
    }


async def scrape_multiple_urls(urls):
    """Scrapes múltiplas URLs e retorna todos os resultados."""
    results = []

    for i, url in enumerate(urls, 1):
        console.print(f"\n{'='*50}")
        console.print(f"[bold blue]📱 Vídeo {i}/{len(urls)}:[/bold blue] {url}")
        console.print(f"{'='*50}")

        result = await scrape_single_url(url)
        results.append(result)

        if result['success']:
            console.print(
                f"[green]✓[/green] Vídeo {i}: "
                f"{len(result['comments'])} comentários extraídos"
            )
        else:
            console.print(f"[red]✗[/red] Vídeo {i}: falha ao extrair comentários")

        # Pequena pausa entre URLs para não sobrecarregar
        if i < len(urls):
            await asyncio.sleep(3)

    return results


if __name__ == '__main__':
    urls = [
        'https://www.tiktok.com/@ricaperrone/video/7645152910459915541',
    ]

    console.print("[bold blue]🎬 TikTok Comments Scraper[/bold blue]")
    results = asyncio.run(scrape_multiple_urls(urls))

    for r in results:
        if r['success']:
            print(f"\nURL: {r['url']}")
            print(f"Comentários: {len(r['comments'])}")
            for i, c in enumerate(r['comments'][:5], 1):
                print(f"  {i}. [{c.get('author', '?')}] {c['text'][:60]}... (❤️ {c.get('likes', 0)})")
