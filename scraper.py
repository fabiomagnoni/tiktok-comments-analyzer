"""
TikTok Comments Scraper - API direta (sem Playwright).
Extrai comentários + respostas aninhadas via API web do TikTok.
Fallback para dados mock quando a API falha.
"""
import json
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
        self._video_url: str = ""  # URL real do vídeo para HTML extraction

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

            # 2. Extrair video ID e username da URL
            video_id, username = self._extract_video_info(url)
            if not video_id:
                raise Exception(f"Não foi possível extrair o video ID de: {url}")

            console.print(f"[blue]🎬[/blue] Video ID: {video_id}, User: @{username or 'unknown'}")

            # Salva a URL real para uso posterior
            self._video_url = url if username else f"https://www.tiktok.com/@{username}/video/{video_id}"

            # 3. Buscar informações do vídeo (likes, favoritos, etc.)
            self._get_video_info(video_id)

            # 4. Buscar todos os comentários com paginação
            top_comments = self._fetch_all_top_comments(video_id)

            console.print(
                f"[blue]📄[/blue] {len(top_comments)} comentários de nível 1"
            )

            # 5. Buscar respostas aninhadas (replies) para cada comentário
            all_comments = []
            for i, comment in enumerate(top_comments):
                all_comments.append(comment)

                reply_count = comment.get("replies_count", 0) or \
                             comment.get("_reply_total", 0)
                if reply_count > 0:
                    try:
                        replies = self._fetch_replies(
                            video_id, comment["_comment_id"]
                        )
                        all_comments.extend(replies)
                        console.print(
                            f"[blue]💬[/blue] Comentário {i+1}: "
                            f"{len(replies)} respostas extraídas"
                        )
                    except Exception as e:
                        console.print(
                            f"[yellow]⚠[/yellow] Erro ao buscar replies "
                            f"do comentário {i+1}: {e}"
                        )

            # Limpa campos internos antes de retornar
            for c in all_comments:
                c.pop("_comment_id", None)
                c.pop("_reply_total", None)
                c.pop("_is_reply", None)

            self.comments = all_comments

            console.print(
                f"[green]✓[/green] {len(self.comments)} comentários "
                f"extraídos (incluindo respostas)!"
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
    # Video ID + Username
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_video_info(url: str) -> tuple:
        """Extrai o video ID e username de uma URL do TikTok.

        Returns:
            (video_id, username) - username pode ser None se não encontrado
        """
        video_id = None
        username = None

        # Padrão principal: /@username/video/VIDEO_ID
        match = re.search(r"/@([^/]+)/video/(\d+)", url)
        if match:
            username = match.group(1)
            video_id = match.group(2)

        # Se não encontrou, tenta só o video ID
        if not video_id:
            match = re.search(r"/video/(\d+)", url)
            if match:
                video_id = match.group(1)

        # Padrão alternativo: ?id=VIDEO_ID ou &id=VIDEO_ID
        if not video_id:
            match = re.search(r"[?&]id=(\d+)", url)
            if match:
                video_id = match.group(1)

        return video_id, username

    # ------------------------------------------------------------------
    # Video Info (likes, favoritos, etc.) - MÚLTIPLAS ESTRATÉGIAS
    # ------------------------------------------------------------------
    def _get_video_info(self, video_id: str):
        """Busca informações do vídeo via múltiplas estratégias."""

        console.print("[blue]📊[/blue] Buscando estatísticas do vídeo...")

        # Estratégia 1: API item/detail
        self._try_api_item_detail(video_id)

        # Estratégia 2: oembed (mais simples, menos dados mas confiável)
        if not self.video_info.get("likes"):
            self._try_oembed(video_id)

        # Estratégia 3: extrair do HTML da página do vídeo (USANDO URL REAL!)
        if not self.video_info.get("likes"):
            self._try_html_extraction(video_id)

        # Debug: mostra o que conseguiu obter
        if self.video_info:
            console.print(f"[blue]📊[/blue] Stats obtidas: {self.video_info}")
        else:
            console.print("[yellow]⚠[/yellow] Nenhuma estatística do vídeo obtida")

    def _try_api_item_detail(self, video_id: str):
        """Tenta obter stats via API item/detail."""
        try:
            headers = self._build_headers()
            url = (
                "https://www.tiktok.com/api/item/detail/"
                f"?aid=1988&item_id={video_id}"
            )

            resp = self.session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                console.print(f"[yellow]⚠[/yellow] API item/detail retornou {resp.status_code}")
                return

            data = resp.json()

            # A estrutura pode variar - tenta múltiplos caminhos
            detail = (data.get("aweme_detail", {}) or
                     data.get("itemInfo", {}).get("itemStruct", {}) or
                     data.get("itemDetail", {}) or
                     data)

            stats = (detail.get("statistics", {}) or
                    detail.get("stats", {}))

            if stats:
                self.video_info.update({
                    "likes": int(stats.get("digg_count", 0) or 0),
                    "comments": int(stats.get("comment_count", 0) or 0),
                    "shares": int(stats.get("share_count", 0) or 0),
                    "favorites": int(stats.get("collect_count", 0) or 0),
                    "plays": int(stats.get("play_count", 0) or 0),
                })

            # Info do autor e descrição
            author = detail.get("author", {}) or {}
            self.video_info.update({
                "title": detail.get("desc", "") or detail.get("description", ""),
                "author_name": author.get("nickname", ""),
                "author_unique_id": author.get("unique_id", ""),
            })

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] API item/detail falhou: {e}")

    def _try_oembed(self, video_id: str):
        """Tenta obter stats via oembed API."""
        try:
            headers = self._build_headers()
            url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@placeholder/video/{video_id}"

            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # oembed tem menos dados mas pode ter título e autor
                if not self.video_info.get("title"):
                    self.video_info["title"] = data.get("title", "")
                if not self.video_info.get("author_name"):
                    self.video_info["author_name"] = data.get("author_name", "")

        except Exception:
            pass

    def _try_html_extraction(self, video_id: str):
        """Tenta extrair stats do HTML da página do vídeo."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            }

            # Usa a URL real do vídeo (com username correto)
            video_url = self._video_url or f"https://www.tiktok.com/@placeholder/video/{video_id}"
            console.print(f"[blue]🌐[/blue] Extraindo HTML de: {video_url}")

            resp = self.session.get(video_url, headers=headers, timeout=20)

            if resp.status_code != 200:
                console.print(f"[yellow]⚠[/yellow] HTML extraction retornou {resp.status_code}")
                return

            html = resp.text

            # Converte valores como "14.4K" para número (14400)
            def parse_count(text):
                """Converte '14.4K' -> 14400, '2.3M' -> 2300000."""
                if not text:
                    return None
                text = text.strip().replace('.', '')  # remove separador de milhar pt-BR
                try:
                    return int(text)
                except ValueError:
                    pass
                # Tenta com sufixo K/M/B
                mult = {'k': 1000, 'm': 1_000_000, 'b': 1_000_000_000}
                upper = text.upper()
                for suffix, factor in mult.items():
                    if upper.endswith(suffix):
                        try:
                            return int(float(upper[:-1]) * factor)
                        except ValueError:
                            pass
                return None

            # Extrai visualizações do HTML (data-e2e="video-views")
            views_match = re.search(r'data-e2e="video-views"[^>]*>([^<]+)</strong>', html)
            if not views_match:
                views_match = re.search(r'aria-label="(\d+[\sKkMmBb]*)\s*Visualizações"', html)
            if views_match and not self.video_info.get("plays"):
                parsed = parse_count(views_match.group(1))
                if parsed:
                    self.video_info["plays"] = parsed

            # Extrai likes do HTML (aria-label="XXXX Curtidas")
            likes_match = re.search(r'aria-label="(\d+)\s*Curtidas"', html)
            if not likes_match:
                likes_match = re.search(r'data-e2e="browse-like-count"[^>]*>(\d+)</strong>', html)
            if likes_match and not self.video_info.get("likes"):
                self.video_info["likes"] = int(likes_match.group(1))

            # Extrai comentários do HTML (Comentários (XX))
            comments_match = re.search(r'Comentários\s*\((\d+)\)', html)
            if not comments_match:
                comments_match = re.search(r'data-e2e="browse-comment-count"[^>]*>(\d+)</strong>', html)
            if comments_match and not self.video_info.get("comments"):
                self.video_info["comments"] = int(comments_match.group(1))

            # Extrai compartilhamentos
            shares_match = re.search(r'aria-label="(\d+)\s*Compartilhamento', html)
            if not shares_match:
                shares_match = re.search(r'data-e2e="browse-share-count"[^>]*>(\d+)</strong>', html)
            if shares_match and not self.video_info.get("shares"):
                self.video_info["shares"] = int(shares_match.group(1))

            # Extrai favoritos
            favs_match = re.search(r'aria-label="(\d+)\s*Favorito', html)
            if not favs_match:
                favs_match = re.search(r'data-e2e="browse-favorite-count"[^>]*>(\d+)</strong>', html)
            if favs_match and not self.video_info.get("favorites"):
                self.video_info["favorites"] = int(favs_match.group(1))

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] HTML extraction falhou: {e}")

    # ------------------------------------------------------------------
    # Comentários de nível 1 (top-level) com paginação
    # ------------------------------------------------------------------
    def _fetch_all_top_comments(self, video_id: str) -> List[Dict[str, Any]]:
        """Busca todos os comentários de nível 1 usando a API do TikTok."""
        all_comments = []
        cursor = 0
        max_pages = 50

        for page in range(max_pages):
            try:
                comments_page = self._fetch_comment_page(video_id, cursor)
                if not comments_page:
                    break

                all_comments.extend(comments_page)
                console.print(
                    f"[blue]📄[/blue] Página {page + 1}: "
                    f"{len(comments_page)} comentários "
                    f"(total nível 1: {len(all_comments)})"
                )

                # Verifica se há mais páginas - múltiplas estratégias
                has_more = self._check_has_more()

                if not has_more:
                    break

                cursor += len(comments_page)
                time.sleep(1.5)  # respeitar rate limit

            except Exception as e:
                console.print(f"[red]✗[/red] Erro na página {page + 1}: {e}")
                if page == 0:
                    break
                time.sleep(3)
                continue

        return all_comments

    def _check_has_more(self) -> bool:
        """Verifica se há mais páginas de comentários."""
        try:
            if not hasattr(self, '_last_response'):
                return False

            data = self._last_response
            if not isinstance(data, dict):
                return False

            # Múltiplas estratégias para detectar hasMore
            checks = [
                data.get("hasMore", False),
                data.get("has_more", False),
                data.get("hasmore", False),
                data.get("HasMore", False),
            ]

            if any(checks):
                return True

            # Se cursor mudou e temos comentários, pode haver mais
            new_cursor = data.get("cursor", 0) or data.get("next_cursor", 0)
            if isinstance(new_cursor, (int, str)) and str(new_cursor).isdigit():
                try:
                    nc = int(new_cursor)
                    if nc > 0:
                        return True
                except ValueError:
                    pass

            # Se a resposta tem menos comentários que o count pedido, é o fim
            comments = data.get("comments", []) or []
            if len(comments) < 30:  # count padrão é 30
                return False

            return True

        except Exception:
            return False

    def _fetch_comment_page(self, video_id: str, cursor: int) -> List[Dict[str, Any]]:
        """Busca uma página de comentários."""
        headers = self._build_headers()

        # Endpoint principal da API web do TikTok para comentários
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
            return []

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

    # ------------------------------------------------------------------
    # Respostas aninhadas (replies) - endpoint separado!
    # ------------------------------------------------------------------
    def _fetch_replies(self, video_id: str, comment_id: str) -> List[Dict[str, Any]]:
        """Busca as respostas de um comentário específico.

        Usa o endpoint /api/comment/list/reply/ que retorna apenas
        as replies de um comentário pai.
        """
        all_replies = []
        cursor = 0
        max_pages = 20  # limite para replies por comentário

        for page in range(max_pages):
            try:
                headers = self._build_headers()
                url = (
                    f"https://www.tiktok.com/api/comment/list/reply/"
                    f"?aid=1988&comment_id={comment_id}"
                    f"&count=30&cursor={cursor}"
                    f"&item_id={video_id}"
                )

                resp = self.session.get(url, headers=headers, timeout=20)

                if resp.status_code != 200:
                    break

                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    break

                reply_list = (data.get("comments", []) or
                            data.get("reply_comment", []) or
                            data.get("replies", []))

                for item in reply_list:
                    r = self._parse_reply_item(item)
                    if r:
                        all_replies.append(r)

                # Verifica se há mais páginas de replies
                has_more = (
                    data.get("hasMore", False) or
                    data.get("has_more", False) or
                    data.get("hasmore", False)
                )

                if not has_more or not reply_list:
                    break

                cursor += len(reply_list)
                time.sleep(0.8)  # rate limit mais leve para replies

            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Erro ao buscar replies "
                              f"(página {page + 1}): {e}")
                break

        return all_replies

    @staticmethod
    def _parse_reply_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrai dados de uma resposta (reply) da API."""
        if not isinstance(item, dict):
            return None

        # Extrair texto com múltiplas estratégias
        text = ""

        val = item.get("text")
        if isinstance(val, str) and len(val.strip()) > 0:
            text = val.strip()

        if not text:
            content = item.get("content")
            if isinstance(content, dict):
                for key in ["text", "content"]:
                    val = content.get(key)
                    if isinstance(val, str) and len(val.strip()) > 0:
                        text = val.strip()
                        break
            elif isinstance(content, str) e
