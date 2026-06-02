"""
TikTok Comments Scraper - Abordagem robusta com múltiplas estratégias de extração.
1) Tenta extrair dados das variáveis JS internas do TikTok (SIGI_STATE, __UNIVERSAL_DATA_FOR_REHYDRATION__)
2) Fallback: tenta seletores DOM
3) Fallback: dump da página para debug
"""
import asyncio
import json
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper de comentários do TikTok usando múltiplas estratégias."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}

    async def _setup_browser(self):
        """Configura o navegador com anti-detecção máxima."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
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

        # Anti-detecção máxima
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            delete navigator.__proto__.webdriver;
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
        """)

        return playwright, browser, context

    async def _extract_from_js_state(self, page):
        """
        Estratégia 1: Extrai dados das variáveis JavaScript internas do TikTok.
        O TikTok armazena TODOS os dados em variáveis globais como:
        - __UNIVERSAL_DATA_FOR_REHYDRATION__
        - SIGI_STATE
        - __INITIAL_STATE__
        """
        try:
            # Extrai o estado completo da aplicação do TikTok
            state = await page.evaluate("""
                () => {
                    const data = {};

                    // Tenta múltiplas fontes de dados internos
                    if (typeof __UNIVERSAL_DATA_FOR_REHYDRATION__ !== 'undefined') {
                        data.universal = JSON.parse(JSON.stringify(__UNIVERSAL_DATA_FOR_REHYDRATION__));
                    }

                    if (typeof SIGI_STATE !== 'undefined') {
                        try {
                            data.sigi = JSON.parse(JSON.stringify(SIGI_STATE));
                        } catch(e) {}
                    }

                    if (typeof __INITIAL_STATE__ !== 'undefined') {
                        data.initial = JSON.parse(JSON.stringify(__INITIAL_STATE__));
                    }

                    // Tenta encontrar dados em qualquer variável global que contenha "comment" ou "Comment"
                    for (const key in window) {
                        try {
                            if (typeof window[key] === 'object' && window[key] !== null) {
                                const str = JSON.stringify(window[key]);
                                if ((str.includes('comment') || str.includes('Comment')) && str.length < 500000) {
                                    data['global_' + key.substring(0, 30)] = window[key];
                                }
                            }
                        } catch(e) {}
                    }

                    return data;
                }
            """)

            if state:
                console.print("[green]✓[/green] Dados JS internos encontrados!")

                # Salva o estado completo em arquivo para debug
                os.makedirs('data', exist_ok=True)
                with open('data/debug_state.json', 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2, default=str)
                console.print("[blue]ℹ️[/blue] Estado completo salvo em data/debug_state.json")

                # Processa os dados para extrair comentários
                comments = self._parse_js_state(state)
                if comments:
                    return comments

            return []

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao extrair JS state: {e}")
            return []

    def _parse_js_state(self, state):
        """Processa o estado JS do TikTok para extrair comentários."""
        comments = []

        # Função recursiva para buscar dados de comentário em objetos aninhados
        def find_comments(obj, depth=0):
            if depth > 15:
                return []

            found = []

            if isinstance(obj, dict):
                # Procura por chaves que contenham "comment" ou "Comment"
                for key, value in obj.items():
                    if 'comment' in key.lower() and isinstance(value, list) and len(value) > 0:
                        found.extend(self._extract_comment_list(value))

                    # Continua recursão em dicts e listas
                    if isinstance(value, (dict, list)):
                        found.extend(find_comments(value, depth + 1))

            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        found.extend(find_comments(item, depth + 1))

            return found

        # Processa cada fonte de dados
        for source_name, source_data in state.items():
            extracted = find_comments(source_data)
            if extracted:
                console.print(f"[green]✓[/green] {len(extracted)} comentários encontrados em '{source_name}'")
                comments.extend(extracted)

        return comments

    def _extract_comment_list(self, items):
        """Extrai dados de uma lista de comentários."""
        results = []

        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                # O TikTok armazena comentários com várias estruturas possíveis
                text = (item.get('text') or
                       item.get('content', {}).get('text', '') or
                       item.get('desc', '') or
                       str(item.get('comment_text', '')))

                if not text or len(str(text)) < 1:
                    continue

                # Extrai autor
                author = (item.get('user') or
                        item.get('user_info', {}).get('unique_id', '') or
                        item.get('author', {}).get('nickname', '') or
                        str(item.get('username', '')))

                if isinstance(author, dict):
                    author = author.get('unique_id', author.get('nickname', ''))

                # Extrai likes
                likes = (int(item.get('digg_count', 0) or
                          item.get('like_count', 0) or
                          item.get('likes', 0)))

                # Extrai respostas
                replies = (int(item.get('reply_comment_total', 0) or
                            item.get('replies', {}).get('total', 0) or
                            item.get('reply_count', 0) or
                            item.get('child_comments', {}).get('total', 0)))

                # Extrai data
                date = (item.get('create_time', '') or
                       item.get('time', ''))

                results.append({
                    'text': str(text),
                    'likes': likes,
                    'replies_count': replies,
                    'author': str(author) if author else '',
                    'date': str(date) if date else '',
                })

            except Exception:
                continue

        return results

    async def _extract_from_dom(self, page):
        """Estratégia 2: Extrai dados do DOM via JavaScript."""
        try:
            raw = await page.evaluate("""
                () => {
                    const comments = [];

                    // Tenta múltiplos seletores
                    const selectors = [
                        '[data-e2e="comment-list"] .comment-item',
                        '[class*="comment-list"] [class*="item"]',
                        '.comment-item',
                        '[class*="CommentItem"]',
                    ];

                    let elements = [];
                    for (const sel of selectors) {
                        const found = document.querySelectorAll(sel);
                        if (found.length > 0) {
                            elements = found;
                            break;
                        }
                    }

                    if (elements.length === 0) return null;

                    elements.forEach(el => {
                        try {
                            // Extrai todo o texto do elemento e seus filhos
                            const allText = el.innerText?.trim() || '';
                            if (!allText) return;

                            // Tenta extrair texto principal (primeiro parágrafo/texto significativo)
                            let textEl = el.querySelector('p, span, [class*="text"], .text');
                            let text = textEl ? textEl.textContent?.trim() : allText.split('\\n')[0];

                            if (!text || text.length < 2) return;

                            // Extrai números (likes e replies) do texto
                            const numbers = allText.match(/\\d+/g) || [];

                            comments.push({
                                text: text.substring(0, 500),
                                likes: parseInt(numbers[0]) || 0,
                                replies_count: parseInt(numbers[1]) || 0,
                                author: '',
                                date: '',
                            });
                        } catch(e) {}
                    });

                    return comments;
                }
            """)

            if raw and len(raw) > 0:
                console.print(f"[green]✓[/green] {len(raw)} comentários extraídos do DOM")
                return raw

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao extrair do DOM: {e}")

        return []

    async def _dump_page_for_debug(self, page):
        """Salva o HTML da página para debug."""
        os.makedirs('data', exist_ok=True)
        try:
            html = await page.content()
            with open('data/debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html[:500000])  # Limita o tamanho
            console.print("[blue]ℹ️[/blue] HTML da página salvo em data/debug_page.html")

            # Salva também um resumo dos elementos encontrados
            summary = await page.evaluate("""
                () => {
                    const info = {};
                    // Conta elementos por classe que contenha "comment"
                    const allElements = document.querySelectorAll('*');
                    const commentRelated = [];
                    allElements.forEach(el => {
                        if (el.className && typeof el.className === 'string' &&
                            el.className.toLowerCase().includes('comment')) {
                            commentRelated.push({
                                tag: el.tagName,
                                class: el.className.substring(0, 100),
                                text: (el.textContent || '').substring(0, 200)
                            });
                        }
                    });
                    info.comment_elements = commentRelated.slice(0, 50);

                    // Lista variáveis globais
                    const globals = [];
                    for (const key in window) {
                        if (key.startsWith('__') || key.includes('STATE') || key.includes('DATA')) {
                            try {
                                globals.push({
                                    name: key,
                                    type: typeof window[key],
                                    size: JSON.stringify(window[key]).length
                                });
                            } catch(e) {}
                        }
                    }
                    info.global_vars = globals;

                    return info;
                }
            """)

            with open('data/debug_summary.json', 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            console.print("[blue]ℹ️[/blue] Resumo salvo em data/debug_summary.json")

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao salvar debug: {e}")

    async def _wait_for_page_load(self, page):
        """Aguarda a página carregar completamente."""
        # Espera por network idle
        try:
            await page.wait_for_load_state('networkidle', timeout=30000)
        except PlaywrightTimeout:
            pass

        # Aguarda um tempo extra para JS processar
        await asyncio.sleep(5)

    async def _click_comments_button(self, page):
        """Tenta clicar no botão de comentários."""
        selectors = [
            '[data-e2e="comment-button"]',
            '[class*="comment-button"]',
            'button[aria-label*="comentário"]',
            'button[aria-label*="Comentário"]',
            'button[aria-label*="comment"]',
        ]

        for sel in selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    console.print(f"[blue]💬[/blue] Clicando no botão de comentários ({sel})...")
                    await btn.click()
                    await asyncio.sleep(3)
                    return True
            except Exception:
                continue

        return False

    async def _scroll_comments(self, page):
        """Rola a página para carregar mais comentários."""
        max_scrolls = 25
        no_change_count = 0

        for i in range(max_scrolls):
            await asyncio.sleep(random.uniform(1.5, 3))

            try:
                # Tenta encontrar o container de comentários
                comment_container = page.locator('[data-e2e="comment-list"]').first
                if not await comment_container.count():
                    break

                last_height = await comment_container.evaluate('el => el.scrollHeight')

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

            except Exception as e:
                break

        return True

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
                response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)

                if not response.ok:
                    console.print(f"[red]✗[/red] Erro HTTP {response.status}")
                    return [], {}

                # Aguarda carregamento completo
                await self._wait_for_page_load(page)

                # Estratégia 1: Extrai das variáveis JS internas (ANTES de clicar em comentários!)
                console.print("[blue]📊[/blue] Tentando extrair dados do estado JS interno...")
                js_comments = await self._extract_from_js_state(page)

                if js_comments:
                    self.comments = js_comments
                    console.print(f"[green]✓[/green] {len(js_comments)} comentários extraídos via JS state!")
                else:
                    # Se não encontrou no JS state, tenta clicar e carregar comentários
                    await self._click_comments_button(page)

                    # Aguarda mais tempo após clicar
                    await asyncio.sleep(5)

                    # Tenta novamente o JS state após clicar
                    console.print("[blue]📊[/blue] Tentando extrair dados do estado JS (2ª tentativa)...")
                    js_comments = await self._extract_from_js_state(page)

                    if js_comments:
                        self.comments = js_comments
                        console.print(f"[green]✓[/green] {len(js_comments)} comentários extraídos via JS state!")
                    else:
                        # Estratégia 2: Extrai do DOM
                        console.print("[blue]📊[/blue] Tentando extrair dados do DOM...")

                        await self._scroll_comments(page)
                        dom_comments = await self._extract_from_dom(page)

                        if dom_comments:
                            self.comments = dom_comments
                        else:
                            # Dump para debug
                            console.print("[red]✗[/red] Nenhum comentário encontrado com nenhuma estratégia!")
                            await self._dump_page_for_debug(page)

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
    """Scrapes uma única URL."""
    scraper = TikTokScraper(headless=True)
    comments, video_info = await scraper.scrape(url)
    return {
        'url': url,
        'comments': comments or [],
        'video_info': video_info or {},
        'success': len(comments) > 0,
    }


async def scrape_multiple_urls(urls):
    """Scrapes múltiplas URLs."""
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
