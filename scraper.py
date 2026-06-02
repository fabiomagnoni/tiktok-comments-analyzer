"""
TikTok Comments Scraper - Intercepta requisições de rede para extrair dados brutos da API interna do TikTok.
Estratégia: captura as chamadas XHR/fetch que o navegador faz ao carregar a página.
"""
import asyncio
import json
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper via interceptação de requisições de rede."""

    def __init__(self, headless=True):
        self.headless = headless
        self.comments = []
        self.video_info = {}
        # Armazena todas as respostas da API interna do TikTok
        self.api_responses = []
        self.intercepted_data = {}

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

        # Anti-detecção
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

    async def _intercept_api_calls(self, page):
        """Intercepta todas as requisições de rede para capturar dados da API."""

        # Intercepta respostas que contenham dados do TikTok
        async def handle_response(response):
            try:
                url = response.url
                status = response.status

                # Filtra URLs relevantes - API interna do TikTok
                if status != 200:
                    return

                # Captura todas as respostas JSON de domínios do TikTok
                is_tiktok_api = any(kw in url for kw in [
                    'tiktok.com/api/',
                    'tiktokv.com/api/',
                    '.tiktok.com/api',
                    '.tiktokv.com/api',
                    '/api/v2/comment/list',
                    '/api/comment/list',
                ])

                # Também captura a página principal (tem dados embutidos)
                is_main_page = 'tiktok.com/@' in url and '/video/' in url

                if not (is_tiktok_api or is_main_page):
                    return

                try:
                    body = await response.text()
                    if len(body) > 500000:
                        body = body[:500000]

                    self.api_responses.append({
                        'url': url,
                        'status': status,
                        'body_preview': body[:2000],
                        'full_body': body,
                    })

                except Exception:
                    pass

            except Exception:
                pass

        page.on('response', handle_response)

    def _parse_api_responses(self):
        """Processa as respostas da API para extrair comentários."""
        comments = []

        for resp in self.api_responses:
            body = resp.get('full_body', '') or ''
            url = resp.get('url', '')

            # Tenta parsear como JSON
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                continue

            # Busca comentários recursivamente no JSON
            found = self._find_comments_in_json(data)
            if found:
                console.print(f"[green]✓[/green] {len(found)} comentários em: {url[:80]}")
                comments.extend(found)

        return comments

    def _find_comments_in_json(self, data):
        """Busca dados de comentário recursivamente em um objeto JSON."""
        results = []

        if isinstance(data, dict):
            # Procura por chaves relacionadas a comentários
            comment_keys = ['comments', 'comment_list', 'comments_list',
                          'reply_comment', 'replies', 'child_comments']

            for key in comment_keys:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        extracted = self._extract_from_list(value)
                        results.extend(extracted)
                    elif isinstance(value, dict):
                        # Pode ter uma sub-chave com a lista real
                        for sub_key, sub_val in value.items():
                            if isinstance(sub_val, list):
                                extracted = self._extract_from_list(sub_val)
                                results.extend(extracted)

            # Continua recursão em todos os valores
            for key, value in data.items():
                if isinstance(value, (dict, list)) and key not in comment_keys:
                    sub_results = self._find_comments_in_json(value)
                    results.extend(sub_results)

        elif isinstance(data, list):
            # Verifica se é uma lista de comentários
            extracted = self._extract_from_list(data)
            if extracted:
                return extracted

            for item in data:
                if isinstance(item, (dict, list)):
                    sub_results = self._find_comments_in_json(item)
                    results.extend(sub_results)

        return results

    def _extract_from_list(self, items):
        """Extrai dados de uma lista que pode conter comentários."""
        results = []

        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                # O TikTok usa várias estruturas - tenta todas
                text = (str(item.get('text', '')) or
                       str(item.get('content', {}).get('text', '') if isinstance(item.get('content'), dict) else '') or
                       str(item.get('desc', '')) or
                       str(item.get('comment_text', '')) or
                       str(item.get('body', '')))

                # Se não tem texto, tenta encontrar qualquer campo string significativo
                if not text:
                    for key in item:
                        val = item[key]
                        if isinstance(val, str) and len(val) > 3 and len(val) < 1000:
                            # Verifica se parece com comentário (não é URL, não é ID numérico)
                            if not val.startswith('http') and not val.isdigit():
                                text = val
                                break

                if not text or len(text) < 2:
                    continue

                # Extrai autor
                author = ''
                user_data = item.get('user', {}) or item.get('user_info', {}) or item.get('author', {})
                if isinstance(user_data, dict):
                    author = (str(user_data.get('unique_id', '')) or
                            str(user_data.get('nickname', '')) or
                            str(user_data.get('username', '')))

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

                results.append({
                    'text': text.strip(),
                    'likes': likes,
                    'replies_count': replies,
                    'author': author.strip() if author else '',
                    'date': str(item.get('create_time', '')) or '',
                })

            except Exception:
                continue

        return results

    async def _extract_from_page_source(self, page):
        """Extrai dados embutidos no HTML da página principal."""
        try:
            # O TikTok embute dados JSON no HTML como <script> tags
            embedded_data = await page.evaluate("""
                () => {
                    const results = [];

                    // Procura por script tags com dados JSON
                    const scripts = document.querySelectorAll('script');
                    for (const script of scripts) {
                        const text = script.textContent || '';

                        // Tenta encontrar __UNIVERSAL_DATA_FOR_REHYDRATION__
                        if (text.includes('__UNIVERSAL_DATA_FOR_REHYDRATION__')) {
                            try {
                                const match = text.match(/__UNIVERSAL_DATA_FOR_REHYDRATION__\\s*=\\s*({.*?});/s);
                                if (match) {
                                    results.push(JSON.parse(match[1]));
                                }
                            } catch(e) {}
                        }

                        // Tenta encontrar SIGI_STATE
                        if (text.includes('SIGI_STATE')) {
                            try {
                                const match = text.match(/SIGI_STATE\\s*=\\s*({.*?});/s);
                                if (match) {
                                    results.push(JSON.parse(match[1]));
                                }
                            } catch(e) {}
                        }

                        // Tenta encontrar dados em qualquer script tag com JSON válido
                        try {
                            const parsed = JSON.parse(text);
                            if (typeof parsed === 'object' && parsed !== null) {
                                results.push(parsed);
                            }
                        } catch(e) {}
                    }

                    return results;
                }
            """)

            for data in embedded_data:
                found = self._find_comments_in_json(data)
                if found:
                    console.print(f"[green]✓[/green] {len(found)} comentários no HTML embutido")
                    return found

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Erro ao extrair do HTML: {e}")

        return []

    async def _wait_for_page_load(self, page):
        """Aguarda a página carregar completamente."""
        try:
            await page.wait_for_load_state('networkidle', timeout=30000)
        except PlaywrightTimeout:
            pass
        await asyncio.sleep(5)

    async def _click_comments_button(self, page):
        """Tenta clicar no botão de comentários."""
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
                    console.print(f"[blue]💬[/blue] Clicando no botão de comentários...")
                    await btn.click()
                    await asyncio.sleep(5)
                    return True
            except Exception:
                continue

        return False

    async def _scroll_comments(self, page):
        """Rola para carregar mais comentários."""
        max_scrolls = 20
        no_change_count = 0

        for i in range(max_scrolls):
            await asyncio.sleep(random.uniform(1.5, 3))

            try:
                container = page.locator('[data-e2e="comment-list"]').first
                if not await container.count():
                    break

                last_height = await container.evaluate('el => el.scrollHeight')

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

        return True

    async def _save_debug_data(self, page):
        """Salva dados de debug para diagnóstico."""
        os.makedirs('data', exist_ok=True)

        # Salva as respostas da API
        if self.api_responses:
            with open('data/debug_api_responses.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'total_responses': len(self.api_responses),
                    'urls': [r['url'] for r in self.api_responses],
                    'first_response_preview': self.api_responses[0].get('body_preview', '')[:5000] if self.api_responses else '',
                }, f, ensure_ascii=False, indent=2)

        # Salva HTML da página
        try:
            html = await page.content()
            with open('data/debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html[:500000])
        except Exception:
            pass

    async def scrape(self, url):
        """Realiza o scraping completo."""
        playwright = None
        browser = None

        with console.status(f"🌐 Acessando: {url}", spinner="dots") as status:
            try:
                # Setup navegador
                playwright, browser, context = await self._setup_browser()
                page = await context.new_page()

                # Configura interceptação de rede ANTES de navegar
                console.print("[blue]🔍[/blue] Configurando interceptação de requisições...")
                await self._intercept_api_calls(page)

                # Acessa a URL
                response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)

                if not response.ok:
                    console.print(f"[red]✗[/red] Erro HTTP {response.status}")
                    return [], {}

                # Aguarda carregamento completo
                await self._wait_for_page_load(page)

                # Tenta extrair das respostas da API (interceptadas)
                console.print("[blue]📊[/blue] Processando dados interceptados...")
                api_comments = self._parse_api_responses()

                if api_comments:
                    self.comments = api_comments
                    console.print(f"[green]✓[/green] {len(api_comments)} comentários via API!")
                else:
                    # Tenta extrair do HTML embutido
                    console.print("[blue]📊[/blue] Tentando dados embutidos no HTML...")
                    html_comments = await self._extract_from_page_source(page)

                    if html_comments:
                        self.comments = html_comments
                        console.print(f"[green]✓[/green] {len(html_comments)} comentários via HTML!")
                    else:
                        # Tenta clicar em comentários e carregar mais dados
                        await self._click_comments_button(page)
                        await asyncio.sleep(3)

                        # Processa novamente após clicar (novas requisições foram feitas)
                        console.print("[blue]📊[/blue] Processando dados pós-clique...")
                        api_comments = self._parse_api_responses()

                        if api_comments:
                            self.comments = api_comments
                            console.print(f"[green]✓[/green] {len(api_comments)} comentários via API (pós-clique)!")
                        else:
                            html_comments = await self._extract_from_page_source(page)
                            if html_comments:
                                self.comments = html_comments

                # Se ainda não tem, tenta scroll e mais requisições
                if not self.comments:
                    console.print("[blue]⬇️[/blue] Rolando para carregar mais...")
                    await self._scroll_comments(page)
                    await asyncio.sleep(3)

                    api_comments = self._parse_api_responses()
                    if api_comments:
                        self.comments = api_comments

                # Debug final se não encontrou nada
                if not self.comments:
                    console.print("[red]✗[/red] Nenhum comentário encontrado!")
                    console.print(f"[blue]ℹ️[/blue] {len(self.api_responses)} requisições interceptadas")
                    await self._save_debug_data(page)

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
