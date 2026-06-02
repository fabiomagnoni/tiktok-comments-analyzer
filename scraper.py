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

            video_url = f"https://www.tiktok.com/@placeholder/video/{video_id}"
            resp = self.session.get(video_url, headers=headers, timeout=20)

            if resp.status_code != 200:
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

        except Exception:
            pass
