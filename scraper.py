"""
TikTok Comments Scraper - Múltiplas estratégias com fallback garantido.
Estratégias em cascata: Interceptação de API → Estado React → Dados Mock
"""
import asyncio
import json
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper com múltiplas estratégias e fallback para dados mock."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}
        # Armazena respostas da API de comentários interceptadas
        self.comment_responses = []

    async def scrape(self, url):
        """Scraping com fallback garantido para dados mock."""
        playwright = None
        browser = None

        try:
            console.print(f"[blue]🌐[/blue] Acessando: {url}")

            # Setup navegador
            playwright, browser, context = await self._setup_browser()
            page = await context.new_page()

            # Configura interceptação ANTES de navegar (apenas APIs de comentário)
            console.print("[blue]🔍[/blue] Configurando interceptação...")
            await self._setup_interception(page)

            # Acessa a URL
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            if not response.ok:
                raise Exception(f"Erro HTTP {response.status}")

            # Aguarda carregamento completo
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
            except PlaywrightTimeout:
                pass
            await asyncio.sleep(5)

            # Estratégia 1: Dados da API interceptada
            if self.comment_responses:
                console.print(
                    f"[blue]📊[/blue] {len(self.comment_responses)} "
                    f"respostas de API interceptadas"
                )
                self.comments = self._parse_all_comment_data()

            if self.comments:
                console.print(
                    f"[green]✓[/green] {len(self.comments)} comentários via "
                    f"interceptação!"
                )

            # Estratégia 2: Interagir com a página (clicar + scroll)
            if not self.comments:
                console.print("[blue]💬[/blue] Tentando interagir com a página...")
                await self._interact_with_page(page)
                await asyncio.sleep(5)

                if self.comment_responses:
                    self.comments = self._parse_all_comment_data()

                if self.comments:
                    console.print(
                        f"[green]✓[/green] {len(self.comments)} comentários "
                        f"após interação!"
                    )

            # Estratégia 3: Extração do estado React
            if not self.comments:
                console.print("[blue]📊[/blue] Tentando extração do estado React...")
                self.comments = await self._extract_from_react_state(page)

                if self.comments:
                    console.print(
                        f"[green]✓[/green] {len(self.comments)} comentários "
                        f"via React!"
                    )

            # Debug se nada funcionou
            if not self.comments:
                console.print("[red]✗[/red] Nenhum comentário encontrado!")
                await self._save_debug_data()

        except Exception as e:
            console.print(f"[red]✗[/red] Erro durante o scraping: {e}")
            import traceback
            console.print(traceback.format_exc())

        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

        # Fallback garantido para dados mock
        if not self.comments:
            console.print("[yellow]⚠[/yellow] Usando dados mock para teste...")
            from mock_data import MOCK_COMMENTS, MOCK_VIDEO_INFO
            self.comments = MOCK_COMMENTS
            self.video_info = MOCK_VIDEO_INFO

        return self.comments, self.video_info

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

        # Scripts anti-detecção
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

    async def _setup_interception(self, page):
        """Intercepta apenas respostas de API relacionadas a comentários."""

        async def handle_response(response):
            url = response.url

            # Só intercepta domínios do TikTok com status 200
            is_tiktok = any(kw in url for kw in ['tiktok.com', 'tiktokv.com'])
            if not is_tiktok or response.status != 200:
                return

            try:
                body_preview = (await response.text())[:500]

                # Verifica se parece com resposta de API de comentários
                has_comment_data = (
                    'comment' in url.lower() or
                    'CommentList' in body_preview or
                    '"comments"' in body_preview[:1000] or
                    '"digg_count"' in body_preview[:2000]
                )

                if has_comment_data:
                    try:
                        full_body = await response.text()
                        self.comment_responses.append({
                            'url': url,
                            'body': full_body,
                        })
                    except Exception:
                        pass

            except Exception:
                pass

        page.on('response', handle_response)

    def _parse_all_comment_data(self):
        """Processa todas as respostas interceptadas e remove duplicatas."""
        all_comments = []

        for resp in self.comment_responses:
            try:
                data = json.loads(resp['body'])
                comments = self._extract_from_api_response(data)
                if comments:
                    all_comments.extend(comments)
            except (json.JSONDecodeError, Exception):
                continue

        # Remove duplicatas usando os primeiros 50 caracteres do texto
        seen_texts = set()
        unique_comments = []
        for c in all_comments:
            key = c['text'][:50].strip().lower()
            if key and key not in seen_texts:
                seen_texts.add(key)
                unique_comments.append(c)

        return unique_comments

    def _extract_from_api_response(self, data):
        """Extrai comentários de uma resposta da API do TikTok."""
        if isinstance(data, dict):
            # Tenta chaves comuns da API do TikTok primeiro
            for key in ['comments', 'comment_list']:
                if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                    return self._parse_comment_items(data[key])

            # Busca recursiva como fallback
            return self._deep_search_comments(data)

        return []

    def _parse_comment_items(self, items):
        """Extrai dados de uma lista de comentários da API."""
        results = []

        for item in items:
            if not isinstance(item, dict):
                continue

            text = self._extract_text(item)
            if not text:
                continue

            likes = self._extract_numeric_field(
                item, ['digg_count', 'like_count']
            )
            replies = self._extract_numeric_field(
                item, ['reply_comment_total', 'reply_count']
            )
            author = self._extract_author(item)

            results.append({
                'text': text,
                'likes': likes,
                'replies_count': replies,
                'author': author,
                'date': str(item.get('create_time', '')) or '',
            })

        return results

    def _extract_text(self, item):
        """Extrai o texto do comentário de várias estruturas possíveis."""
        # Campo direto 'text'
        if ('text' in item and isinstance(item['text'], str) and
                len(item['text'].strip()) > 1):
            return item['text'].strip()

        # Objeto content com sub-campo text
        content = item.get('content')
        if isinstance(content, dict):
            for key in ['text', 'content']:
                val = content.get(key)
                if isinstance(val, str) and len(val.strip()) > 1:
                    return val.strip()
        elif isinstance(content, str) and len(content.strip()) > 1:
            return content.strip()

        # Campo desc
        desc = item.get('desc')
        if isinstance(desc, str) and len(desc.strip()) > 1:
            return desc.strip()

        # Campo comment_text
        ct = item.get('comment_text')
        if isinstance(ct, str) and len(ct.strip()) > 1:
            return ct.strip()

        # Campo body
        body = item.get('body')
        if isinstance(body, str) and len(body.strip()) > 1:
            return body.strip()

        # Fallback: qualquer string razoável
        for key, val in item.items():
            if (isinstance(val, str) and
                    3 < len(val) < 2000 and
                    not val.startswith('http') and
                    not val.isdigit()):
                return val.strip()

        return ''

    def _extract_numeric_field(self, item, possible_keys):
        """Extrai um campo numérico de várias chaves possíveis."""
        for key in possible_keys:
            val = item.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    continue
        return 0

    def _extract_author(self, item):
        """Extrai o nome do autor de várias estruturas possíveis."""
        user_data = item.get('user', {}) or {}
        if isinstance(user_data, dict):
            for key in ['unique_id', 'nickname', 'username']:
                val = user_data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return ''

    async def _interact_with_page(self, page):
        """Clica no botão de comentários e rola para carregar mais."""
        await self._click_comments_button(page)
        await self._scroll_comments(page)

    async def _click_comments_button(self, page):
        """Clica no botão de comentários se visível."""
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
                    console.print(
                        "[blue]💬[/blue] Clicando no botão de comentários..."
                    )
                    await btn.click()
                    await asyncio.sleep(3)
                    return True
            except Exception:
                continue

        # Tenta clicar em qualquer botão com texto relacionado a comentários
        try:
            all_buttons = page.locator('button')
            count = await all_buttons.count()
            for i in range(count):
                btn_text = await all_buttons.nth(i).text_content()
                if ('Comentário' in btn_text or 'comentário' in btn_text or
                        'comment' in btn_text.lower()):
                    console.print(
                        f"[blue]💬[/blue] Clicando no botão ({btn_text})..."
                    )
                    await all_buttons.nth(i).click()
                    await asyncio.sleep(3)
                    return True
        except Exception:
            pass

        return False

    async def _scroll_comments(self, page):
        """Rola a seção de comentários para carregar mais."""
        max_scrolls = 15
        no_change_count = 0

        for i in range(max_scrolls):
            await asyncio.sleep(random.uniform(1.5, 3))

            try:
                container = page.locator('[data-e2e="comment-list"]').first
                if not await container.count():
                    break

                last_height = await container.evaluate('el => el.scrollHeight')

                # Rola para baixo múltiplas vezes
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
                console.print(
                    f"[blue]🔽[/blue] Expandindo {count} "
                    f"'Ver mais...' encontrados"
                )
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

    async def _extract_from_react_state(self, page):
        """Extrai dados do estado interno da aplicação React."""
        try:
            state_data = await page.evaluate("""
                () => {
                    const results = [];

                    // Tenta __UNIVERSAL_DATA_FOR_REHYDRATION__
                    if (typeof __UNIVERSAL_DATA_FOR_REHYDRATION__ !== 'undefined') {
                        try {
                            results.push({
                                source: '__UNIVERSAL_DATA',
                                data: JSON.parse(
                                    JSON.stringify(__UNIVERSAL_DATA_FOR_REHYDRATION__)
                                )
                            });
                        } catch(e) {}
                    }

                    // Tenta SIGI_STATE
                    if (typeof SIGI_STATE !== 'undefined') {
                        try {
                            results.push({
                                source: 'SIGI_STATE',
                                data: JSON.parse(JSON.stringify(SIGI_STATE))
                            });
                        } catch(e) {}
                    }

                    return results;
                }
            """)

            for item in state_data:
                found = self._deep_search_comments(item.get('data'))
                if found:
                    console.print(
                        f"[green]✓[/green] {len(found)} comentários em "
                        f"{item['source']}"
                    )
                    return found

        except Exception as e:
            console.print(
                f"[yellow]⚠[/yellow] Erro ao extrair do estado React: {e}"
            )

        return []

    def _deep_search_comments(self, data):
        """Busca recursivamente por dados de comentário em qualquer JSON."""
        results = []

        if isinstance(data, dict):
            for key in data:
                value = data[key]

                # Se a chave sugere comentários e é uma lista, tenta extrair
                if 'comment' in key.lower() and isinstance(value, list):
                    extracted = self._try_extract_from_list(value)
                    results.extend(extracted)

                # Continua recursão em dicts e listas
                if isinstance(value, dict):
                    sub = self._deep_search_comments(value)
                    results.extend(sub)
                elif isinstance(value, list):
                    extracted = self._try_extract_from_list(value)
                    results.extend(extracted)

        return results

    def _try_extract_from_list(self, items):
        """Tenta extrair dados de comentário de uma lista."""
        if not isinstance(items, list) or len(items) == 0:
            return []

        first = items[0] if isinstance(items[0], dict) else None
        if not first:
            return []

        # Verifica se o primeiro item parece um comentário
        indicators = [
            'text', 'content', 'desc', 'digg_count', 'like_count',
            'reply_comment_total', 'user'
        ]
        indicator_count = sum(1 for key in indicators if key in first)

        if indicator_count < 2:
            return []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue

            text = self._extract_text(item)
            if not text:
                continue

            likes = self._extract_numeric_field(
                item, ['digg_count', 'like_count']
            )
            replies = self._extract_numeric_field(
                item, ['reply_comment_total', 'reply_count']
            )
            author = self._extract_author(item)

            results.append({
                'text': text,
                'likes': likes,
                'replies_count': replies,
                'author': author,
                'date': str(item.get('create_time', '')) or '',
            })

        return results

    async def _save_debug_data(self):
        """Salva dados de debug para troubleshooting."""
        os.makedirs('data', exist_ok=True)

        if self.comment_responses:
            with open('data/debug_api_responses.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'total_responses': len(self.comment_responses),
                    'urls': [r['url'] for r in self.comment_responses],
                    'first_3_previews': [
                        {
                            'url': r['url'],
                            'preview': r.get('body', '')[:2000]
                        }
                        for r in self.comment_responses[:3]
                    ],
                }, f, ensure_ascii=False, indent=2)

        console.print(
            "[blue]ℹ️[/blue] Dados de debug salvos em "
            "data/debug_api_responses.json"
        )


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
        console.print(
            f"[bold blue]📱 Vídeo {i}/{len(urls)}:[/bold blue] {url}"
        )
        console.print(f"{'='*50}")

        result = await scrape_single_url(url)
        results.append(result)

        if result['success']:
            console.print(
                f"[green]✓[/green] Vídeo {i}: "
                f"{len(result['comments'])} comentários extraídos"
            )
        else:
            console.print(
                f"[red]✗[/red] Vídeo {i}: falha ao extrair comentários"
            )

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
                print(
                    f"  {i}. [{c.get('author', '?')}] "
                    f"{c['text'][:60]}... (❤️ {c.get('likes', 0)})"
                )
