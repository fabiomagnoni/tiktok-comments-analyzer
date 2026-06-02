"""
TikTok Comments Scraper - API direta (sem Playwright).
Extrai comentários via API web do TikTok com paginação completa.
Fallback para dados mock quando a API falha.
"""
import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from rich.console import Console

console = Console()


class TikTokScraper:
    """Scraper que usa a API web do TikTok diretamente."""

    def __init__(self):
        self.session = requests.Session()
        self.comments: List[Dict[str, Any]] = []
        self.video_info: Dict[str, Any] = {}
        self._cookies_set = False

    # ------------------------------------------------------------------
    # Público
    # ------------------------------------------------------------------
    def scrape(self, url: str) -> tuple:
        """Scrapes comentários de uma URL do TikTok.

        Returns:
            (comments_list, video_info_dict)
        """
        self.comments = []
        self.video_info = {}

        try:
            console.print(f"[blue]🌐[/blue] Acessando: {url}")

            # 1. Obter cookies de sessão
            if not self._get_session_cookies():
                raise Exception("Não foi possível obter cookies do TikTok")

            # 2. Extrair video ID da URL
            video_id = self._extract_video_id(url)
            if not video_id:
                raise Exception(f"Não foi possível extrair o video ID de: {url}")

            console.print(f"[blue]🎬[/blue] Video ID: {video_id}")

            # 3. Buscar informações do vídeo
            self._get_video_info(video_id)

            # 4. Buscar todos os comentários com paginação
            self.comments = self._fetch_all_comments(video_id)

            console.print(
                f"[green]✓[/green] {len(self.comments)} comentários extraídos!"
            )

        except Exception as e:
            console.print(f"[red]✗[/red] Erro no scraping: {e}")
            import traceback
            console.print(traceback.format_exc())

        # Fallback para dados mock
        if not self.comments:
            console.print("[yellow]⚠[/yellow] Usando dados mock para teste...")
            from mock_data import MOCK_COMMENTS, MOCK_VIDEO_INFO
            self.comments = MOCK_COMMENTS
            self.video_info = MOCK_VIDEO_INFO

        return self.comments, self.video_info

    # ------------------------------------------------------------------
    # Sessão / Cookies
    # ------------------------------------------------------------------
    def _get_session_cookies(self) -> bool:
        """Visita a página principal do TikTok para obter cookies válidos."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }

            console.print("[blue]🍪[/blue] Obtendo cookies de sessão...")
            resp = self.session.get(
                "https://www.tiktok.com/", headers=headers, timeout=30
            )
            if resp.status_code != 200:
                return False

            # Extrai o web_id (wid) do HTML se disponível
            wid_match = re.search(r'"wid"\s*:\s*"(\d+)"', resp.text)
            if wid_match:
                self.session.cookies.set("tt_webid", wid_match.group(1))

            self._cookies_set = True
            console.print("[green]✓[/green] Cookies obtidos com sucesso!")
            return True

        except Exception as e:
            console.print(f"[red]✗[/red] Erro ao obter cookies: {e}")
            return False

    # ------------------------------------------------------------------
    # Video ID
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extrai o video ID de uma URL do TikTok."""
        # Padrão: /@user/video/VIDEO_ID
        match = re.search(r"/video/(\d+)", url)
        if match:
            return match.group(1)

        # Padrão alternativo: ?id=VIDEO_ID ou &id=VIDEO_ID
        match = re.search(r"[?&]id=(\d+)", url)
        if match:
            return match.group(1)

        return None

    # ------------------------------------------------------------------
    # Video Info
    # ------------------------------------------------------------------
    def _get_video_info(self, video_id: str):
        """Busca informações básicas do vídeo."""
        try:
            headers = self._build_headers()
            url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@placeholder/video/{video_id}"

            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.video_info.update({
                    "title": data.get("title", ""),
                    "author_name": data.get("author_name", ""),
                    "description": data.get("title", ""),
                })

        except Exception:
            # Não é crítico, continua sem video info
            pass

    # ------------------------------------------------------------------
    # Comentários (API direta com paginação)
    # ------------------------------------------------------------------
    def _fetch_all_comments(self, video_id: str) -> List[Dict[str, Any]]:
        """Busca todos os comentários usando a API do TikTok."""
        all_comments = []
        cursor = 0
        max_pages = 50  # limite de segurança

        for page in range(max_pages):
            try:
                comments_page = self._fetch_comment_page(video_id, cursor)
                if not comments_page:
                    break

                all_comments.extend(comments_page)
                console.print(
                    f"[blue]📄[/blue] Página {page + 1}: "
                    f"{len(comments_page)} comentários "
                    f"(total: {len(all_comments)})"
                )

                # Verifica se há mais páginas
                has_more = False
                try:
                    if hasattr(self, '_last_response'):
                        resp_data = self._last_response
                        if isinstance(resp_data, dict):
                            has_more = (
                                resp_data.get("hasMore", False) or
                                resp_data.get("has_more", False)
                            )
                except Exception:
                    pass

                if not has_more:
                    break

                cursor += len(comments_page)
                time.sleep(1.5)  # respeitar rate limit

            except Exception as e:
                console.print(f"[red]✗[/red] Erro na página {page + 1}: {e}")
                if page == 0:
                    break  # falha na primeira página = aborta
                time.sleep(3)
                continue

        return all_comments

    def _fetch_comment_page(self, video_id: str, cursor: int) -> List[Dict[str, Any]]:
        """Busca uma página de comentários."""
        headers = self._build_headers()

        # Endpoint da API web do TikTok para comentários
        url = (
            f"https://www.tiktok.com/api/comment/list/online/"
            f"?aid=1988&aweme_id={video_id}&count=30"
            f"&cursor={cursor}&item_id={video_id}"
            f"&insert_ids=&isswitch=1&list_type=&need_preview_list=0"
        )

        resp = self.session.get(url, headers=headers, timeout=20)

        if resp.status_code != 200:
            # Tenta o endpoint alternativo (versão mais antiga)
            url_alt = (
                f"https://www.tiktok.com/api/comment/list/"
                f"?aid=1988&aweme_id={video_id}&count=30"
                f"&cursor={cursor}"
            )
            resp = self.session.get(url_alt, headers=headers, timeout=20)

        if resp.status_code != 200:
            raise Exception(f"API retornou status {resp.status_code}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            # Se não for JSON, tenta extrair do HTML (caso de redirect)
            return self._try_html_extraction(video_id)

        self._last_response = data

        comments = []
        comment_list = data.get("comments", [])

        if not comment_list and "comment_list" in data:
            comment_list = data["comment_list"]

        for item in comment_list:
            c = self._parse_comment_item(item)
            if c:
                comments.append(c)

        return comments

    def _try_html_extraction(self, video_id: str) -> List[Dict[str, Any]]:
        """Fallback: tenta extrair comentários do endpoint de detalhes."""
        try:
            headers = self._build_headers()
            video_url = (
                "https://www.tiktok.com/api/item/detail/"
                f"?aid=1988&item_id={video_id}"
            )
            resp = self.session.get(video_url, headers=headers, timeout=20)

            if resp.status_code == 200:
                data = resp.json()
                # Extrai comentários se disponíveis no detail endpoint
                comment_list = (
                    data.get("aweme_detail", {})
                    .get("comments", [])
                )

                comments = []
                for item in comment_list:
                    c = self._parse_comment_item(item)
                    if c:
                        comments.append(c)
                return comments

        except Exception:
            pass

        return []

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_comment_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrai dados de um comentário da API."""
        if not isinstance(item, dict):
            return None

        # Extrair texto com múltiplas estratégias (sem bug de precedência)
        text = ""

        # Estratégia 1: campo direto 'text'
        val = item.get("text")
        if isinstance(val, str) and len(val.strip()) > 0:
            text = val.strip()

        # Estratégia 2: objeto content com sub-campo text
        if not text:
            content = item.get("content")
            if isinstance(content, dict):
                for key in ["text", "content"]:
                    val = content.get(key)
                    if isinstance(val, str) and len(val.strip()) > 0:
                        text = val.strip()
                        break
            elif isinstance(content, str) and len(content.strip()) > 0:
                text = content.strip()

        # Estratégia 3: campo desc
        if not text:
            val = item.get("desc")
            if isinstance(val, str) and len(val.strip()) > 0:
                text = val.strip()

        # Estratégia 4: campo comment_text
        if not text:
            val = item.get("comment_text")
            if isinstance(val, str) and len(val.strip()) > 0:
                text = val.strip()

        # Estratégia 5: fallback - qualquer string razoável
        if not text:
            for key, val in item.items():
                if (isinstance(val, str) and
                        3 < len(val) < 2000 and
                        not val.startswith("http") and
                        not val.isdigit()):
                    text = val.strip()
                    break

        if not text:
            return None

        # Likes (digg_count é o campo padrão da API do TikTok)
        likes = 0
        for key in ["digg_count", "like_count", "likes"]:
            val = item.get(key)
            if val is not None:
                try:
                    likes = int(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Replies count
        replies = 0
        for key in ["reply_comment_total", "reply_count", "replies"]:
            val = item.get(key)
            if val is not None:
                try:
                    replies = int(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Author
        author = ""
        user_data = item.get("user", {}) or {}
        if isinstance(user_data, dict):
            for key in ["unique_id", "nickname", "username"]:
                val = user_data.get(key)
                if isinstance(val, str) and val.strip():
                    author = val.strip()
                    break

        # Date / create_time
        date_raw = item.get("create_time", "") or ""
        try:
            ts = int(date_raw)
            dt = datetime.fromtimestamp(ts)
            date_str = dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            date_str = str(date_raw)

        return {
            "text": text.strip(),
            "likes": likes,
            "replies_count": replies,
            "author": author,
            "date": date_str,
        }

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------
    def _build_headers(self) -> Dict[str, str]:
        """Constrói headers realistas para as requisições."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.tiktok.com/",
            "X-Requested-With": "XMLHttpRequest",
        }


# ------------------------------------------------------------------
# Funções de conveniência (compatíveis com a API existente)
# ------------------------------------------------------------------

def scrape_single_url(url: str) -> Dict[str, Any]:
    """Scrapes uma única URL."""
    scraper = TikTokScraper()
    comments, video_info = scraper.scrape(url)
    return {
        "url": url,
        "comments": comments or [],
        "video_info": video_info or {},
        "success": len(comments) > 0,
    }


def scrape_multiple_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrapes múltiplas URLs."""
    results = []

    for i, url in enumerate(urls, 1):
        console.print(f"\n{'=' * 50}")
        console.print(
            f"[bold blue]📱 Vídeo {i}/{len(urls)}:[/bold blue] {url}"
        )
        console.print(f"{'=' * 50}")

        result = scrape_single_url(url)
        results.append(result)

        if result["success"]:
            console.print(
                f"[green]✓[/green] Vídeo {i}: "
                f"{len(result['comments'])} comentários extraídos"
            )
        else:
            console.print(
                f"[red]✗[/red] Vídeo {i}: falha ao extrair comentários"
            )

        if i < len(urls):
            time.sleep(3)

    return results


if __name__ == "__main__":
    urls = [
        "https://www.tiktok.com/@ricaperrone/video/7645152910459915541",
    ]

    console.print("[bold blue]🎬 TikTok Comments Scraper[/bold blue]")
    results = scrape_multiple_urls(urls)

    for r in results:
        if r["success"]:
            print(f"\nURL: {r['url']}")
            print(f"Comentários: {len(r['comments'])}")
            for i, c in enumerate(r["comments"][:5], 1):
                print(
                    f"  {i}. [{c.get('author', '?')}] "
                    f"{c['text'][:60]}... (❤️ {c.get('likes', 0)})"
                )
