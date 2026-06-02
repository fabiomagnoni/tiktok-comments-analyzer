"""
TikTok Comments Scraper using Playwright
Contorna o WAF do TikTok usando navegador real (Chromium)
"""
import asyncio
import json
import time
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

class TikTokScraper:
    """Scraper de comentários do TikTok usando Playwright."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}

    async def _setup_browser(self):
        """Configura o navegador com headers realistas."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='pt-BR',
        )

        # Evitar detecção de automação
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)

        return playwright, browser, context

    async def _wait_for_comments(self, page):
        """Aguarda os comentários carregarem na página."""
        try:
            # Espera pelo container de comentários
            await page.wait_for_selector('[data-e2e="comment-list"]', timeout=30000)
            console.print("[green]✓[/green] Container de comentários encontrado")
        except PlaywrightTimeout:
            console.print("[yellow]⚠[/yellow] Timeout esperando comentários, tentando alternativa...")
            try:
                await page.wait_for_selector('.comment-list', timeout=15000)
            except PlaywrightTimeout:
                console.print("[red]✗[/red] Não foi possível encontrar os comentários")
                return False
        return True

    async def _scroll_comments(self, page):
        """Rola a página para carregar mais comentários."""
        scroll_count = 0
        max_scrolls = 15

        while scroll_count < max_scrolls:
            await asyncio.sleep(random.uniform(1, 3))

            try:
                comment_container = page.locator('[data-e2e="comment-list"]')
                if not await comment_container.count():
                    break

                last_height = await comment_container.evaluate('el => el.scrollHeight')

                for _ in range(3):
                    await comment_container.evaluate('el => el.scrollTop += 500')
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                new_height = await comment_container.evaluate('el => el.scrollHeight')

                if new_height == last_height:
                    scroll_count += 2
                else:
                    scroll_count += 1

            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Erro ao rolar: {e}")
                break

        return True

    async def _extract_comments(self, page):
        """Extrai os comentários do DOM via JavaScript no navegador."""
        comments_data = []

        try:
            raw_comments = await page.evaluate("""
                () => {
                    const commentElements = document.querySelectorAll('[data-e2e="comment-list"] .comment-item, [class*="comment"]');
                    const comments = [];

                    commentElements.forEach(el => {
                        try {
                            let textEl = el.querySelector('[data-e2e="comment-text"], [class*="comment-text"], .text, p, span');
                            let text = '';
                            if (textEl) text = textEl.textContent?.trim() || '';

                            let likeEl = el.querySelector('[data-e2e="like-count"], [class*="like"], .count');
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

                            let replyEl = el.querySelector('[data-e2e="reply-count"], [class*="reply"]');
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

                            let authorEl = el.querySelector('[data-e2e="comment-author"], [class*="author"], .username');
                            let author = '';
                            if (authorEl) author = authorEl.textContent?.trim() || '';

                            let dateEl = el.querySelector('[data-e2e="comment-time"], [class*="time"]');
                            let date = '';
                            if (dateEl) date = dateEl.textContent?.trim() || '';

                            const replyElements = el.querySelectorAll('[data-e2e="reply-list"] .comment-item, [class*="reply"][class*="item"]');
                            const subComments = [];
                            replyElements.forEach(replyEl => {
                                try {
                                    let rText = replyEl.querySelector('p, span, .text')?.textContent?.trim() || '';
                                    let rAuthor = replyEl.querySelector('.username, [class*="author"]')?.textContent?.trim() || '';
                                    if (rText) subComments.push({ author: rAuthor, text: rText });
                                } catch(e) {}
                            });

                            if (text) {
                                comments.push({
                                    text: text,
                                    likes: likes,
                                    replies_count: replies,
                                    author: author,
                                    date: date,
                                    sub_comments: subComments
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

        except Exception as e:
            console.print(f"[red]✗[/red] Erro ao extrair comentários: {e}")

        return comments_data

    async def _extract_video_info(self, page):
        """Extrai informações do vídeo."""
        try:
            video_data = await page.evaluate("""
                () => {
                    const info = {};
                    const likeBtn = document.querySelector('[data-e2e="like-button"]');
                    if (likeBtn) {
                        const countEl = likeBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.likes = countEl.textContent?.trim() || '';
                    }
                    const commentBtn = document.querySelector('[data-e2e="comment-button"]');
                    if (commentBtn) {
                        const countEl = commentBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.comment_count = countEl.textContent?.trim() || '';
                    }
                    const shareBtn = document.querySelector('[data-e2e="share-button"]');
                    if (shareBtn) {
                        const countEl = shareBtn.querySelector('.count, [class*="count"]');
                        if (countEl) info.shares = countEl.textContent?.trim() || '';
                    }
                    const descEl = document.querySelector('[data-e2e="video-desc"], .desc, [class*="description"]');
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

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Iniciando scraper...", total=None)

            try:
                progress.update(task, description="🌐 Iniciando navegador...")
                playwright, browser, context = await self._setup_browser()

                page = await context.new_page()

                progress.update(task, description=f"📱 Acessando {url}")
                response = await page.goto(url, wait_until='networkidle', timeout=60000)

                if not response.ok:
                    console.print(f"[red]✗[/red] Erro ao carregar página: HTTP {response.status}")
                    return []

                progress.update(task, description="⏳ Aguardando carregamento...")
                await asyncio.sleep(5)

                # Tenta clicar no botão de comentários se necessário
                try:
                    comment_btn = page.locator('[data-e2e="comment-button"]')
                    if await comment_btn.count() > 0:
                        progress.update(task, description="💬 Abrindo seção de comentários...")
                        await comment_btn.click()
                        await asyncio.sleep(3)
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Não foi possível clicar no botão: {e}")

                progress.update(task, description="📋 Carregando comentários...")
                if not await self._wait_for_comments(page):
                    return []

                progress.update(task, description="🎬 Extraindo informações do vídeo...")
                await self._extract_video_info(page)

                progress.update(task, description="⬇️ Rolando para carregar mais comentários...")
                await self._scroll_comments(page)

                progress.update(task, description="📝 Extraindo comentários...")
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

    def get_results(self):
        """Retorna os resultados do scraping."""
        return {
            'comments': self.comments,
            'video_info': self.video_info,
            'total_comments': len(self.comments),
        }


async def scrape_tiktok(url, headless=True):
    """Função principal para scraping."""
    scraper = TikTokScraper(headless=headless)
    return await scraper.scrape(url)


if __name__ == '__main__':
    url = 'https://www.tiktok.com/@ricaperrone/video/7645152910459915541'
    console.print(f"[bold blue]Scraping TikTok:[/bold blue] {url}")
    comments, video_info = asyncio.run(scrape_tiktok(url))

    if comments:
        print(f"\nTotal de comentários: {len(comments)}")
        for i, c in enumerate(comments[:10], 1):
            print(f"{i}. [{c.get('author', '?')}] {c['text'][:80]}... (❤️ {c.get('likes', 0)})")
    else:
        console.print("[red]Nenhum comentário encontrado[/red]")
