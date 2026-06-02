"""
TikTok Comments Scraper - Intercepta TODAS as requisições de rede + extrai do estado React.
Estratégias em cascata até encontrar os comentários.
"""
import asyncio
import json
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper via interceptação de rede + extração do estado React."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}
        # Armazena TODAS as respostas da API
        self.api_responses = []

    async def _setup_browser(self):
        """Configura o navegador com anti-detecção."""
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

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR','pt','en-US','en']
            });
        """)

        return playwright, browser, context

    async def _intercept_all_responses(self, page):
        """Intercepta TODAS as respostas de rede."""

        async def handle_response(response):
            try:
                url = response.url
                status = response.status

                if status != 200:
                    return

                # Captura TODOS os domínios do TikTok
                is_tiktok = any(kw in url for kw in [
                    'tiktok.com', 'tiktokv.com', 'musical.ly'
                ])

                if not is_tiktok:
                    return

                try:
                    body = await response.text()
                    # Salva tudo que seja JSON ou contenha dados relevantes
                    should_save = (
                        '/api/' in url or
                        len(body) < 500000 or
                        'comment' in body.lower()[:2000] or
                        'Comment' in body[:2000]
                    )

                    if should_save:
                        self.api_responses.append({
                            'url': url,
                            'status': status,
                            'body_preview': body[:3000],
                            'full_body': body,
                        })

                except Exception:
                    pass

            except Exception:
                pass

        page.on('response', handle_response)

    def _parse_all_responses(self):
        """Processa TODAS as respostas para encontrar comentários."""
        all_comments = []

        for resp in self.api_responses:
            body = resp.get('full_body', '') or ''
            url = resp.get('url', '')

            # Tenta parsear como JSON
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                continue

            # Busca comentários recursivamente
            found = self._deep_search_comments(data)
            if found:
                console.print(f"[green]✓[/green] {len(found)} comentários em: {url[:100]}")
                all_comments.extend(found)

        return all_comments

    def _deep_search_comments(self, data):
        """Busca recursivamente por dados de comentário em qualquer estrutura JSON."""
        results = []

        if isinstance(data, dict):
            # Chaves que podem conter listas de comentários
            comment_list_keys = [
                'comments', 'comment_list', 'comments_list',
                'reply_comment', 'replies', 'child_comments',
                'comment', 'Comments', 'CommentList',
            ]

            for key in data:
                value = data[key]

                # Se a chave sugere comentários e é uma lista, tenta extrair
                if any(kw in key.lower() for kw in ['comment', 'reply']) and isinstance(value, list):
                    extracted = self._try_extract_comments_from_list(value)
                    results.extend(extracted)

                # Continua recursão em dicts e listas (limita profundidade)
                if isinstance(value, dict):
                    sub = self._deep_search_comments(value)
                    results.extend(sub)
                elif isinstance(value, list):
                    # Se é uma lista de dicts com texto, pode ser comentários
                    extracted = self._try_extract_comments_from_list(value)
                    results.extend(extracted)

        return results

    def _try_extract_comments_from_list(self, items):
        """Tenta extrair dados de comentário de uma lista."""
        if not isinstance(items, list) or len(items) == 0:
            return []

        # Verifica se o primeiro item parece um comentário (tem campos típicos)
        first = items[0] if isinstance(items[0], dict) else None
        if not first:
            return []

        comment_indicators = [
            'text', 'content', 'desc', 'comment_text', 'body',
            'user', 'author', 'digg_count', 'like_count',
            'reply_comment_total', 'create_time',
        ]

        # Conta quantos indicadores de comentário existem no primeiro item
        indicator_count = sum(1 for key in comment_indicators if key in first)

        # Se tem pelo menos 2 indicadores, provavelmente é uma lista de comentários
        if indicator_count < 2:
            return []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                comment = self._parse_single_comment(item)
                if comment:
                    results.append(comment)
            except Exception:
                continue

        return results

    def _parse_single_comment(self, item):
        """Extrai dados de um único comentário."""
        if not isinstance(item, dict):
            return None

        try:
            # Extrai texto - tenta múltiplas chaves
            text = ''
            for key in ['text', 'content', 'desc', 'comment_text', 'body']:
                val = item.get(key)
                if isinstance(val, str) and len(val.strip()) > 1:
                    text = val.strip()
                    break
                elif isinstance(val, dict):
                    # content pode ser um objeto com sub-chave 'text'
                    for sub_key in ['text', 'content']:
                        sub_val = val.get(sub_key)
                        if isinstance(sub_val, str) and len(sub_val.strip()) > 1:
                            text = sub_val.strip()
                            break

            # Se ainda não tem texto, tenta encontrar qualquer string significativa
            if not text:
                for key, val in item.items():
                    if (isinstance(val, str) and
                        len(val) > 3 and len(val) < 2000 and
                        not val.startswith('http') and
                        not val.isdigit() and
                        'tiktok' not in val.lower()):
                        text = val.strip()
                        break

            if not text:
                return None

            # Extrai autor
            author = ''
            user_data = item.get('user', {}) or item.get('user_info', {}) or item.get('author', {})
            if isinstance(user_data, dict):
                for key in ['unique_id', 'nickname', 'username', 'name']:
                    val = user_data.get(key)
                    if isinstance(val, str) and val.strip():
                        author = val.strip()
                        break

            # Extrai likes
            likes = 0
            for key in ['digg_count', 'like_count', 'likes', 'liked_count']:
                val = item.get(key)
                if val is not None:
                    try:
                        likes = int(val)
                        break
                    except (ValueError, TypeError):
                        continue

            # Extrai respostas
            replies = 0
            for key in ['reply_comment_total', 'reply_count', 'replies']:
                val = item.get(key)
                if val is not None:
                    try:
                        replies = int(val)
                        break
                    except (ValueError, TypeError):
                        continue

            return {
                'text': text,
                'likes': likes,
                'replies_count': replies,
                'author': author,
                'date': str(item.get('create_time', '')) or '',
            }

        except Exception:
            return None

    async def _extract_from_react_state(self, page):
        """Extrai dados do estado interno da aplicação React do TikTok."""
        try:
            state_data = await page.evaluate("""
                () => {
                    const results = [];

                    // Tenta extrair de __UNIVERSAL_DATA_FOR_REHYDRATION__
                    if (typeof __UNIVERSAL_DATA_FOR_REHYDRATION__ !== 'undefined') {
                        try {
                            results.push({
                                source: '__UNIVERSAL_DATA',
                                data: JSON.parse(JSON.stringify(__UNIVERSAL_DATA_FOR_REHYDRATION__))
                            });
                        } catch(e) {}
                    }

                    // Tenta extrair de SIGI_STATE
                    if (typeof SIGI_STATE !== 'undefined') {
                        try {
                            results.push({
                                source: 'SIGI_STATE',
                                data: JSON.parse(JSON.stringify(SIGI_STATE))
                            });
                        } catch(e) {}
                    }

                    // Tenta extrair de __INITIAL_STATE__
                    if (typeof __INITIAL_STATE__ !== 'undefined') {
                        try {
                            results.push({
                                source: '__INITIAL_STATE__',
                                data: JSON.parse(JSON.stringify(__INITIAL_STATE__))
                            });
                        } catch(e) {}
                    }

                    // Tenta encontrar dados em script tags embutidos
                    const scripts = document.querySelectorAll('script');
                    for (const script of scripts) {
                        const text = script.textContent || '';
                        if (text.includes('__UNIVERSAL_DATA_FOR_REHYDRATION__')) {
                            try {
                                const match = text.match(/__UNIVERSAL_DATA_FOR_REHYDRATION__\\s*=\\s*({.*?});/s);
                                if (match) {
                                    results.push({
                                        source: 'script_tag_universal',
                                        data: JSON.parse(match[1])
                                    });
                                }
                            } catch(e) {}
                        }
                    }

                    return results;
                }
            """)

            for item in state_data:
                found = self._deep_search_comments(item.get('data'))
                if found:
                    console.print(f"[green]✓[/green] {len(found)} comentários em {item['source']}")
                    return found

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao extrair do estado React: {e}")

        return []

    async def _click_comments_button(self, page):
        """Clica no botão de comentários."""
        selectors = [
            '[data-e2e="comment-button"]',
            'button[aria-label*="comentário" i]',
            'button[aria-label*="Comentário" i]',
            'button[aria-label*="comment" i]',
        ]

        for sel in selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    console.print("[blue]💬[/blue] Clicando no botão de comentários...")
                    await btn.click()
                    await asyncio.sleep(5)
                    return True
            except Exception:
                continue

        # Tenta clicar em qualquer botão que tenha "21" ou número próximo (número de comentários)
        try:
            all_buttons = page.locator('button')
            count = await all_buttons.count()
            for i in range(count):
                btn_text = await all_buttons.nth(i).text_content()
                if 'Comentário' in btn_text or 'comentário' in btn_text:
                    console.print(f"[blue]💬[/blue] Clicando no botão de comentários (texto: {btn_text})...")
                    await all_buttons.nth(i).click()
                    await asyncio.sleep(5)
                    return True
        except Exception:
            pass

        return False

    async def _scroll_and_expand(self, page):
        """Rola e expande comentários com 'Ver mais...'."""
        max_scrolls = 20
        no_change_count = 0

        for i in range(max_scrolls):
            await asyncio.sleep(random.uniform(1.5, 3))

            try:
                container = page.locator('[data-e2e="comment-list"]').first
                if not await container.count():
                    break

                last_height = await container.evaluate('el => el.scrollHeight')

                # Rola para baixo
                for _ in range(3):
                    await container.evaluate('el => el.scrollTop += 600')
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                new_height = await container.evaluate('el => el.scrollHeight')

                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        return True
                else:
                    no_change_count = 0

            except Exception:
                break

        # Tenta clicar em "Ver mais..." para expandir respostas
        try:
            ver_mais = page.locator('text=/Ver mais/i')
            count = await ver_mais.count()
            if count > 0:
                console.print(f"[blue]🔽[/blue] Expandindo {count} 'Ver mais...' encontrados")
                for i in range(min(count, 10)):
                    try:
                        btn = ver_mais.nth(0)
                        await btn.click()
                        await asyncio.sleep(2)
                    except Exception:
                        break
        except Exception:
            pass

        return True

    async def _save_debug_data(self):
        """Salva dados de debug."""
        os.makedirs('data', exist_ok=True)

        if self.api_responses:
            with open('data/debug_api_responses.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'total_responses': len(self.api_responses),
                    'urls': [r['url'] for r in self.api_responses],
                    'first_3_previews': [
                        {
                            'url': r['url'],
                            'preview': r.get('body_preview', '')[:2000]
                        }
                        for r in self.api_responses[:3]
                    ],
                }, f, ensure_ascii=False, indent=2)

    async def scrape(self, url):
        """Realiza o scraping completo."""
        playwright = None
        browser = None

        with console.status(f"🌐 Acessando: {url}", spinner="dots") as status:
            try:
                # Setup navegador
                playwright, browser, context = await self._setup_browser()
                page = await context.new_page()

                # Configura interceptação ANTES de navegar
                console.print("[blue]🔍[/blue] Configurando interceptação de rede...")
                await self._intercept_all_responses(page)

                # Acessa a URL
                response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)

                if not response.ok:
                    console.print(f"[red]✗[/red] Erro HTTP {response.status}")
                    return [], {}

                # Aguarda carregamento completo
                try:
                    await page.wait_for_load_state('networkidle', timeout=30000)
                except PlaywrightTimeout:
                    pass
                await asyncio.sleep(5)

                # Estratégia 1: Extrai das respostas da API interceptadas
                console.print("[blue]📊[/blue] Processando dados da API...")
                api_comments = self._parse_all_responses()

                if api_comments:
                    self.comments = api_comments
                    console.print(f"[green]✓[/green] {len(api_comments)} comentários via API!")
                else:
                    # Estratégia 2: Extrai do estado React
                    console.print("[blue]📊[/blue] Tentando estado React...")
                    react_comments = await self._extract_from_react_state(page)

                    if react_comments:
                        self.comments = react_comments
                        console.print(f"[green]✓[/green] {len(react_comments)} comentários via React!")
                    else:
                        # Estratégia 3: Clica em comentários e tenta novamente
                        await self._click_comments_button(page)

                        # Aguarda novas requisições
                        await asyncio.sleep(5)

                        console.print("[blue]📊[/blue] Processando dados pós-clique...")
                        api_comments = self._parse_all_responses()

                        if api_comments:
                            self.comments = api_comments
                            console.print(f"[green]✓[/green] {len(api_comments)} comentários via API (pós-clique)!")
                        else:
                            react_comments = await self._extract_from_react_state(page)
                            if react_comments:
                                self.comments = react_comments

                # Estratégia 4: Scroll e expande "Ver mais..."
                if not self.comments:
                    console.print("[blue]⬇️[/blue] Rolando e expandindo...")
                    await self._scroll_and_expand(page)
                    await asyncio.sleep(3)

                    api_comments = self._parse_all_responses()
                    if api_comments:
                        self.comments = api_comments

                # Debug final
                if not self.comments:
                    console.print("[red]✗[/red] Nenhum comentário encontrado!")
                    console.print(f"[blue]ℹ️[/blue] {len(self.api_responses)} requisições interceptadas")
                    await self._save_debug_data()

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
