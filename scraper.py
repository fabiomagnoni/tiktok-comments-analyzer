```
TikTok Comments Scraper - API direta (sem Playwright).
Extrai comentarios + respostas aninhadas via API web do TikTok.
Fallback para dados mock quando a API falha.
```
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

    # ------------------------------------------------------------------
    # Publico
    # ------------------------------------------------------------------
    def scrape(self, url: str) -> tuple:
        """Scrapes comentarios de uma URL do TikTok.

        Returns:
            (comments_list, video_info_dict)
        """
        self.comments = []
        self.video_info = {}

        try:
            console.print(f"[blue]🌐[/blue] Acessando: {url}")

            # 1. Obter cookies de sessao
            if not self._get_session_cookies():
                raise Exception("Nao foi possivel obter cookies do TikTok")

            # 2. Extrair video ID da URL
            video_id = self._extract_video_id(url)
            if not video_id:
                raise Exception(f"Nao foi possivel extrair o video ID de: {url}")

            console.print(f"[blue]🎬[/blue] Video ID: {video_id}")

            # 3. Buscar informacoes do video (likes, favoritos, etc.)
            self._get_video_info(video_id, url)

            # 4. Buscar todos os comentarios com paginacao
            top_comments = self._fetch_all_top_comments(video_id)

            console.print(
                f"[blue]📄[/blue] {len(top_comments)} comentarios de nivel 1"
            )

            # 5. Buscar respostas aninhadas (replies) para cada comentario
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
                            f"[blue]💬[/blue] Comentario {i+1}: "
                            f"{len(replies)} respostas extraidas"
                        )
                    except Exception as e:
                        console.print(
                            f"[yellow]⚠[/yellow] Erro ao buscar replies "
                            f"do comentario {i+1}: {e}"
                        )

            # Limpa campos internos antes de retornar
            for c in all_comments:
                c.pop("_comment_id", None)
                c.pop("_reply_total", None)
                c.pop("_is_reply", None)

            self.comments = all_comments

            console.print(
                f"[green]✓[/green] {len(self.comments)} comentarios "
                f"extraidos (incluindo respostas)!"
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
    # Sessao / Cookies
    # ------------------------------------------------------------------
    def _get_session_cookies(self) -> bool:
        """Visita a pagina principal do TikTok para obter cookies validos."""
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

            console.print("[blue]🍪[/blue] Obtendo cookies de sessao...")
            resp = self.session.get(
                "https://www.tiktok.com/", headers=headers, timeout=30
            )
            if resp.status_code != 200:
                return False

            # Extrai o web_id (wid) do HTML se disponivel
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
        match = re.search(r"/video/(\d+)", url)
        if match:
            return match.group(1)

        match = re.search(r"[?&]id=(\d+)", url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _extract_username(url: str) -> Optional[str]:
        """Extrai o username de uma URL do TikTok."""
        match = re.search(r"/@([^/]+)/video/", url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def parse_count(text: str) -> int:
        """Converte numeros abreviados para inteiros.

        Exemplos: "14.4K" -> 14400, "2.3M" -> 2300000, "1.5B" -> 1500000000
                 "14,4K" -> 14400 (virgula como separador decimal)
        """
        if not text:
            return 0
        text = text.strip().upper()

        try:
            # Se ja e um numero puro (sem sufixo K/M/B)
            if text.replace(",", "").replace(".", "").isdigit():
                # "1.234" -> 1234 ou "1,234" -> 1234
                return int(text.replace(".", "").replace(",", ""))

            # Extrair sufixo e multiplicador
            multiplier = 1
            if text.endswith("K"):
                multiplier = 1_000
                text = text[:-1].strip()
            elif text.endswith("M"):
                multiplier = 1_000_000
                text = text[:-1].strip()
            elif text.endswith("B"):
                multiplier = 1_000_000_000
                text = text[:-1].strip()

            # Tratar separador decimal: virgula -> ponto, depois remover pontos milhar
            text = text.replace(",", ".")
            # Se tem mais de um ponto, o primeiro e separador de milhar
            parts = text.split(".")
            if len(parts) > 2:
                text = "".join(parts)  # remover todos os pontos (milhar)
            return int(float(text) * multiplier)
        except (ValueError, TypeError):
            return 0

    # ------------------------------------------------------------------
    # Video Info (likes, favoritos, etc.) - MULTIPLES ESTRATEGIAS
    # ------------------------------------------------------------------
    def _get_video_info(self, video_id: str, url: str = ""):
        """Busca informacoes do video via multiplas estrategias."""

        # Extrair username da URL para usar nas requisicoes
        username = self._extract_username(url) if url else "placeholder"

        # Estrategia 1: API item/detail
        self._try_api_item_detail(video_id)

        # Estrategia 2: oembed (mais simples, menos dados mas confiavel)
        self._try_oembed(username, video_id)

        # Estrategia 3: extrair do HTML da pagina do video (com username real)
        # Roda sempre para tentar completar campos faltantes
        self._try_html_extraction(username, video_id)

        # Estrategia 4: embed v2 API (dados em camelCase - confiavel!)
        if not self.video_info.get("likes") or not self.video_info.get("plays"):
            self._try_embed_v2(video_id)

        # Estrategia 5: extrair stats do JSON embutido na pagina (SSR data)
        if not self.video_info.get("likes") or not self.video_info.get("plays"):
            self._try_ssr_json_extraction(username, video_id)

    def _try_api_item_detail(self, video_id: str):
        """Tenta obter stats via API item/detail."""
        try:
            headers = self._build_headers()
            api_url = (
                "https://www.tiktok.com/api/item/detail/"
                f"?aid=1988&item_id={video_id}"
            )

            resp = self.session.get(api_url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return

            data = resp.json()

            # A estrutura pode variar - tenta multiplos caminhos
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

            # Info do autor e descricao
            author = detail.get("author", {}) or {}
            self.video_info.update({
                "title": detail.get("desc", "") or detail.get("description", ""),
                "author_name": author.get("nickname", ""),
                "author_unique_id": author.get("unique_id", ""),
            })

        except Exception:
            pass

    def _try_oembed(self, username: str, video_id: str):
        """Tenta obter stats via oembed API."""
        try:
            headers = self._build_headers()
            safe_username = username or "placeholder"
            api_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{safe_username}/video/{video_id}"

            resp = self.session.get(api_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # oembed tem menos dados mas pode ter titulo e autor
                if not self.video_info.get("title"):
                    self.video_info["title"] = data.get("title", "")
                if not self.video_info.get("author_name"):
                    self.video_info["author_name"] = data.get("author_name", "")

        except Exception:
            pass

    def _try_html_extraction(self, username: str, video_id: str):
        """Tenta extrair stats do HTML da pagina do video."""
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

            safe_username = username or "placeholder"
            video_url = f"https://www.tiktok.com/@{safe_username}/video/{video_id}"
            resp = self.session.get(video_url, headers=headers, timeout=20)

            if resp.status_code != 200:
                return

            html = resp.text

            # --- Extrai Visualizacoes (Views/Plays) ---
            plays_value = None

            # Padrao 1: <strong data-e2e="video-views">14.4K</strong>
            views_match = re.search(
                r'data-e2e="video-views"[^>]*>([^<]+)</strong>', html
            )
            if views_match:
                plays_value = self.parse_count(views_match.group(1))

            # Padrao 2: aria-label com Visualizacoes (pode ter numero abreviado)
            if not plays_value:
                views_aria = re.search(
                    r'aria-label="([\d.,]+[\sKkMmBb]*)\s*Visualiza', html
                )
                if views_aria:
                    plays_value = self.parse_count(views_aria.group(1))

            # Padrao 3: aria-label com Views (ingles)
            if not plays_value:
                views_en = re.search(
                    r'aria-label="([\d.,]+[\sKkMmBb]*)\s*Views', html
                )
                if views_en:
                    plays_value = self.parse_count(views_en.group(1))

            # Padrao 4: play_count no JSON embutido da pagina
            if not plays_value:
                play_json = re.search(r'"play_count":\s*(\d+)', html)
                if play_json:
                    plays_value = int(play_json.group(1))

            if plays_value and plays_value > 0 and not self.video_info.get("plays"):
                self.video_info["plays"] = plays_value

            # --- Extrai Likes (Curtidas) ---
            likes_value = None

            # Padrao 1: aria-label="XXXX Curtidas"
            likes_match = re.search(r'aria-label="(\d+)\s*Curtidas"', html)
            if likes_match:
                likes_value = int(likes_match.group(1))

            # Padrao 2: data-e2e="browse-like-count">XXX</strong>
            if not likes_value:
                likes_e2e = re.search(
                    r'data-e2e="browse-like-count"[^>]*>(\d+)</strong>', html
                )
                if likes_e2e:
                    likes_value = int(likes_e2e.group(1))

            # Padrao 3: aria-label com Likes (ingles)
            if not likes_value:
                likes_en = re.search(r'aria-label="(\d+)\s*Likes"', html)
                if likes_en:
                    likes_value = int(likes_en.group(1))

            # Padrao 4: digg_count no JSON embutido da pagina
            if not likes_value:
                digg_json = re.search(r'"digg_count":\s*(\d+)', html)
                if digg_json:
                    val = int(digg_json.group(1))
                    # Verificar se e do video (nao de um comentario - valores pequenos sao suspeitos)
                    if val >= 10:
                        likes_value = val

            if likes_value and likes_value > 0 and not self.video_info.get("likes"):
                self.video_info["likes"] = likes_value

            # --- Extrai Comentarios ---
            comments_value = None

            # Padrao 1: Comentarios (XX) - com e sem acento
            comments_match = re.search(r'[Cc]oment[aeáários]+\s*\((\d+)\)', html)
            if not comments_match:
                comments_match = re.search(
                    r'Comments?\s*\((\d+)\)', html, re.IGNORECASE
                )
            if comments_match:
                comments_value = int(comments_match.group(1))

            # Padrao 2: data-e2e="browse-comment-count"
            if not comments_value:
                comments_e2e = re.search(
                    r'data-e2e="browse-comment-count"[^>]*>(\d+)</strong>', html
                )
                if comments_e2e:
                    comments_value = int(comments_e2e.group(1))

            # Padrao 3: comment_count no JSON embutido
            if not comments_value:
                comment_json = re.search(r'"comment_count":\s*(\d+)', html)
                if comment_json:
                    comments_value = int(comment_json.group(1))

            if comments_value and comments_value > 0 and not self.video_info.get("comments"):
                self.video_info["comments"] = comments_value

            # --- Extrai Compartilhamentos ---
            shares_match = re.search(r'aria-label="(\d+)\s*Compartilhamento', html)
            if not shares_match:
                shares_match = re.search(r'data-e2e="browse-share-count"[^>]*>(\d+)</strong>', html)
            if shares_match and not self.video_info.get("shares"):
                self.video_info["shares"] = int(shares_match.group(1))

            # --- Extrai Favoritos ---
            favs_match = re.search(r'aria-label="(\d+)\s*Favorito', html)
            if not favs_match:
                favs_match = re.search(r'data-e2e="browse-favorite-count"[^>]*>(\d+)</strong>', html)
            if favs_match and not self.video_info.get("favorites"):
                self.video_info["favorites"] = int(favs_match.group(1))

        except Exception:
            pass

    def _try_embed_v2(self, video_id: str):
        """Tenta obter stats via embed v2 API (dados em camelCase)."""
        try:
            headers = self._build_headers()
            url = f"https://www.tiktok.com/embed/v2/{video_id}"

            resp = self.session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return

            html = resp.text

            # O embed v2 usa camelCase para os campos de stats
            # diggCount, playCount, commentCount, shareCount, collectCount

            # Extrai likes (diggCount)
            if not self.video_info.get("likes"):
                digg_match = re.search(r'"diggCount"\s*:\s*(\d+)', html)
                if digg_match:
                    val = int(digg_match.group(1))
                    if val > 0:
                        self.video_info["likes"] = val

            # Extrai visualizacoes (playCount)
            if not self.video_info.get("plays"):
                play_match = re.search(r'"playCount"\s*:\s*(\d+)', html)
                if play_match:
                    val = int(play_match.group(1))
                    if val > 0:
                        self.video_info["plays"] = val

            # Extrai comentarios (commentCount)
            if not self.video_info.get("comments"):
                comment_match = re.search(r'"commentCount"\s*:\s*(\d+)', html)
                if comment_match:
                    val = int(comment_match.group(1))
                    if val > 0:
                        self.video_info["comments"] = val

            # Extrai compartilhamentos (shareCount) - aceita 0 como valor valido
            if "shares" not in self.video_info:
                share_match = re.search(r'"shareCount"\s*:\s*(\d+)', html)
                if share_match:
                    self.video_info["shares"] = int(share_match.group(1))

            # Extrai favoritos (collectCount) - pode nao existir no embed
            if not self.video_info.get("favorites"):
                collect_match = re.search(r'"collectCount"\s*:\s*(\d+)', html)
                if collect_match:
                    val = int(collect_match.group(1))
                    if val > 0:
                        self.video_info["favorites"] = val

            # Info do video (itemInfos)
            item_infos = re.search(r'"itemInfos"\s*:\s*\{([^}]*)\}', html)
            if item_infos:
                item_data = item_infos.group(1)
                if not self.video_info.get("title"):
                    text_match = re.search(r'"text"\s*:\s*"([^"]*)"', item_data)
                    if text_match:
                        self.video_info["title"] = text_match.group(1)

        except Exception:
            pass

    def _try_ssr_json_extraction(self, username: str, video_id: str):
        """Tenta extrair stats do JSON SSR embutido na pagina (UNIVERSAL_DATA/SIGI-State)."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                    "AppleWebKit/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            }

            safe_username = username or "placeholder"
            video_url = f"https://www.tiktok.com/@{safe_username}/video/{video_id}"
            resp = self.session.get(video_url, headers=headers, timeout=20)

            if resp.status_code != 200:
                return

            html = resp.text

            # Tentar extrair UNIVERSAL_DATA ou SIGI-State
            json_raw = None

            univ_match = re.search(
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
                html, re.DOTALL
            )
            if univ_match:
                json_raw = univ_match.group(1).strip().rstrip(";").strip()

            if not json_raw:
                sigi_match = re.search(
                    r'<script id="SIGI-State"[^>]*>(.*?)</script>',
                    html, re.DOTALL
                )
                if sigi_match:
                    json_raw = sigi_match.group(1).strip().rstrip(";").strip()

            if not json_raw or len(json_raw) < 50:
                return

            data = json.loads(json_raw)

            # Navegar pelo JSON para encontrar o video com aweme_id
            def find_video(obj, target_id, depth=0):
                if depth > 40:
                    return None
                if isinstance(obj, dict):
                    if obj.get("aweme_id") == target_id or obj.get("id") == target_id:
                        # Verificar se tem statistics (e o video, nao um comentario)
                        stats = obj.get("statistics", {}) or obj.get("stats", {})
                        if stats:
                            return obj
                    for k, v in list(obj.items())[:100]:
                        result = find_video(v, target_id, depth + 1)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj[:200]:
                        result = find_video(item, target_id, depth + 1)
                        if result:
                            return result
                return None

            import sys
            old_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(500)

            video_obj = find_video(data, video_id)

            sys.setrecursionlimit(old_limit)

            if not video_obj:
                # Tentar encontrar por caminho conhecido (webapp.detail.initialData.itemInfo)
                webapp = data.get("__DEFAULT_SCOPE__", {}).get(
                    "webapp.detail.initialData", {}
                )
                if not webapp:
                    webapp = data.get("webapp.app-detail-initial-data", {})

                item_info = (
                    webapp.get("itemInfo", {}).get("itemStruct", {}) or
                    webapp.get("itemDetail", {}) or
                    webapp
                )

                stats = (
                    item_info.get("statistics", {}) or
                    item_info.get("stats", {})
                )

                if stats:
                    video_obj = item_info

            if video_obj and isinstance(video_obj, dict):
                stats = video_obj.get("statistics", {}) or video_obj.get("stats", {})

                if stats:
                    # Extrai likes
                    digg = int(stats.get("digg_count", 0) or 0)
                    if digg > 0 and not self.video_info.get("likes"):
                        self.video_info["likes"] = digg

                    # Extrai comentarios
                    comment_c = int(stats.get("comment_count", 0) or 0)
                    if comment_c > 0 and not self.video_info.get("comments"):
                        self.video_info["comments"] = comment_c

                    # Extrai compartilhamentos
                    share_c = int(stats.get("share_count", 0) or 0)
                    if share_c > 0 and not self.video_info.get("shares"):
                        self.video_info["shares"] = share_c

                    # Extrai favoritos
                    collect_c = int(stats.get("collect_count", 0) or 0)
                    if collect_c > 0 and not self.video_info.get("favorites"):
                        self.video_info["favorites"] = collect_c

                    # Extrai visualizacoes
                    play_c = int(stats.get("play_count", 0) or 0)
                    if play_c > 0 and not self.video_info.get("plays"):
                        self.video_info["plays"] = play_c

                # Info do autor e descricao
                if not self.video_info.get("title"):
                    desc = video_obj.get("desc", "") or video_obj.get("description", "")
                    if desc:
                        self.video_info["title"] = desc

                author = video_obj.get("author", {}) or {}
                if isinstance(author, dict):
                    if not self.video_info.get("author_name"):
                        nick = author.get("nickname", "") or author.get("nickname_text", "")
                        if nick:
                            self.video_info["author_name"] = nick

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Comentarios de nivel 1 (top-level) com paginacao
    # ------------------------------------------------------------------
    def _fetch_all_top_comments(self, video_id: str) -> List[Dict[str, Any]]:
        """Busca todos os comentarios de nivel 1 usando a API do TikTok."""
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
                    f"[blue]📄[/blue] Pagina {page + 1}: "
                    f"{len(comments_page)} comentarios "
                    f"(total nivel 1: {len(all_comments)})"
                )

                # Verifica se ha mais paginas - multiplas estrategias
                has_more = self._check_has_more()

                if not has_more:
                    break

                cursor += len(comments_page)
                time.sleep(1.5)  # respeitar rate limit

            except Exception as e:
                console.print(f"[red]✗[/red] Erro na pagina {page + 1}: {e}")
                if page == 0:
                    break
                time.sleep(3)
                continue

        return all_comments

    def _check_has_more(self) -> bool:
        """Verifica se ha mais paginas de comentarios."""
        try:
            if not hasattr(self, '_last_response'):
                return False

            data = self._last_response
            if not isinstance(data, dict):
                return False

            # Multiplas estrategias para detectar hasMore
            checks = [
                data.get("hasMore", False),
                data.get("has_more", False),
                data.get("hasmore", False),
                data.get("HasMore", False),
            ]

            if any(checks):
                return True

            # Se cursor mudou e temos comentarios, pode haver mais
            new_cursor = data.get("cursor", 0) or data.get("next_cursor", 0)
            if isinstance(new_cursor, (int, str)) and str(new_cursor).isdigit():
                try:
                    nc = int(new_cursor)
                    if nc > 0:
                        return True
                except ValueError:
                    pass

            # Se a resposta tem menos comentarios que o count pedido, e o fim
            comments = data.get("comments", []) or []
            if len(comments) < 30:  # count padrao e 30
                return False

            return True

        except Exception:
            return False

    def _fetch_comment_page(self, video_id: str, cursor: int) -> List[Dict[str, Any]]:
        """Busca uma pagina de comentarios."""
        headers = self._build_headers()

        # Endpoint principal da API web do TikTok para comentarios
        url = (
            f"https://www.tiktok.com/api/comment/list/online/"
            f"?aid=1988&aweme_id={video_id}&count=30"
            f"&cursor={cursor}&item_id={video_id}"
            f"&insert_ids=&isswitch=1&list_type=&need_preview_list=0"
        )

        resp = self.session.get(url, headers=headers, timeout=20)

        if resp.status_code != 200:
            # Tenta o endpoint alternativo (versao mais antiga)
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
        """Busca as respostas de um comentario especifico.

        Usa o endpoint /api/comment/list/reply/ que retorna apenas
        as replies de um comentario pai.
        """
        all_replies = []
        cursor = 0
        max_pages = 20  # limite para replies por comentario

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

                # Verifica se ha mais paginas de replies
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
                              f"(pagina {page + 1}): {e}")
                break

        return all_replies

    @staticmethod
    def _parse_reply_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrai dados de uma resposta (reply) da API."""
        if not isinstance(item, dict):
            return None

        # Extrair texto com multiplas estrategias
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
            elif isinstance(content, str) and len(content.strip()) > 0:
                text = content.strip()

        if not text:
            val = item.get("desc")
            if isinstance(val, str) and len(val.strip()) > 0:
                text = val.strip()

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

        # Likes
        likes = 0
        for key in ["digg_count", "like_count", "likes"]:
            val = item.get(key)
            if val is not None:
                try:
                    likes = int(val)
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

        # Date
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
            "replies_count": 0,  # replies nao tem sub-replies neste nivel
            "author": author,
            "date": date_str,
        }

    # ------------------------------------------------------------------
    # Parsing de comentarios de nivel 1
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_comment_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrai dados de um comentario da API."""
        if not isinstance(item, dict):
            return None

        # Extrair texto com multiplas estrategias
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
            elif isinstance(content, str) and len(content.strip()) > 0:
                text = content.strip()

        if not text:
            val = item.get("desc")
            if isinstance(val, str) and len(val.strip()) > 0:
                text = val.strip()

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

        # Likes (digg_count e o campo padrao da API do TikTok)
        likes = 0
        for key in ["digg_count", "like_count", "likes"]:
            val = item.get(key)
            if val is not None:
                try:
                    likes = int(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Replies count - armazena em campo interno tambem para uso posterior
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

        # Salva o comment_id internamente para buscar replies depois
        comment_id = item.get("cid", "") or ""

        return {
            "text": text.strip(),
            "likes": likes,
            "replies_count": replies,
            "_reply_total": replies,  # copia interna para uso no scraper
            "_comment_id": comment_id,  # ID interno para buscar replies
            "author": author,
            "date": date_str,
        }

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------
    def _build_headers(self) -> Dict[str, str]:
        """Construi headers realistas para as requisicoes."""
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
# Funcoes de conveniencia (compativeis com a API existente)
# ------------------------------------------------------------------

def scrape_single_url(url: str) -> Dict[str, Any]:
    """Scrapes uma unica URL."""
    scraper = TikTokScraper()
    comments, video_info = scraper.scrape(url)
    return {
        "url": url,
        "comments": comments or [],
        "video_info": video_info or {},
        "success": len(comments) > 0,
    }


def scrape_multiple_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrapes multiplas URLs."""
    results = []

    for i, url in enumerate(urls, 1):
        console.print(f"\n{'=' * 50}")
        console.print(
            f"[bold blue]📱 Video {i}/{len(urls)}:[/bold blue] {url}"
        )
        console.print(f"{'=' * 50}")

        result = scrape_single_url(url)
        results.append(result)

        if result["success"]:
            console.print(
                f"[green]✓[/green] Video {i}: "
                f"{len(result['comments'])} comentarios extraidos"
            )
        else:
            console.print(
                f"[red]✗[/red] Video {i}: falha ao extrair comentarios"
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
            print(f"Comentarios: {len(r['comments'])}")
            vi = r.get("video_info", {})
            if vi:
                print(f"  ❤️ Likes do video: {vi.get('likes', 'N/A')}")
                print(f"  💬 Comentarios: {vi.get('comments', 'N/A')}")
                print(f"  🔖 Favoritos: {vi.get('favorites', 'N/A')}")
                print(f"  🔄 Compartilhamentos: {vi.get('shares', 'N/A')}")
            for i, c in enumerate(r["comments"][:5], 1):
                print(
                    f"  {i}. [{c.get('author', '?')}] "
                    f"{c['text'][:60]}... (❤️ {c.get('likes', 0)})"
                )