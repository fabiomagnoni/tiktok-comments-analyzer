# TikTok Comments Analyzer — CLAUDE.md

## Project Overview

Dashboard web para análise de comentários e sentimento de vídeos do TikTok. Usuário cola URLs de vídeos, o sistema faz scraping dos comentários via API web do TikTok, roda análise de sentimento PT/EN e gera visualizações (word cloud, gráficos, top comments). Pensado para CMOs e equipes de marketing avaliarem potencial de influencers como espaço publicitário.

**Stack:** Python 3 · Flask · requests · TextBlob · NLTK · WordCloud · Matplotlib · Chart.js (frontend vanilla JS)

**Rodar local:** `pip install -r requirements.txt && python app.py` → http://localhost:5000

---

## Arquitetura

```
app.py          → Flask: rotas HTTP, cache JSON, threading, export CSV/PDF, sessões
scraper.py      → TikTokScraper: API web TikTok, extração de comentários + video_info
analyzer.py     → SentimentAnalyzer + WordCloudGenerator + run_aggregated_analysis()
insights.py     → Insights de marketing (CMO): engagement, purchase intent, idioma,
                  tópicos, brand safety, ad potential. stdlib (+ langdetect opcional)
mock_data.py    → MOCK_COMMENTS / MOCK_VIDEO_INFO para testes sem scraping
templates/index.html  → SPA: toda a UI em HTML/JS puro com Chart.js
static/         → wordcloud.png (+ wordcloud_<vid>.png por vídeo) gerados em runtime
data/           → results.json (cache) e sessions/ (snapshots), gitignored
IMPLEMENTATION_PLAN.md → tracking vivo da implementação (fases, decisões, changelog)
```

### Fluxo de dados
```
POST /api/scrape
  → scrape_multiple_urls() [scraper.py]
     → TikTokScraper.scrape() por URL
        → _get_video_info(): 4 estratégias em cascata
        → _fetch_all_top_comments(): paginação cursor-based (max 50 páginas × 30)
        → _fetch_replies(): aninhadas para cada comentário com replies
  → run_aggregated_analysis() [analyzer.py]
     → run_analysis() por URL + agregado
        → SentimentAnalyzer.analyze_all() → polarity + label
        → WordCloudGenerator.generate() → static/wordcloud.png
  → save_results() → data/results.json
  → JSON → renderDashboard() [JS]
```

---

## Modelo de Dados

### `video_info` (por vídeo, do scraper)
```python
{
    "likes": 13_600_000,       # diggCount
    "comments": 66_451,        # commentCount (total TikTok, não o scrapeado!)
    "shares": 412_400,         # shareCount
    "favorites": 698_600,      # collectCount
    "plays": 123_600_000,      # playCount
    "title": "descrição do vídeo",
    "author_name": "Nome do criador",
    "author_unique_id": "username"
}
```

### `summary` (resultado da análise)
```python
{
    "total_comments": 8658,    # comentários SCRAPEADOS (≠ video_info.comments!)
    "positive_count": 315,
    "negative_count": 41,
    "neutral_count": 8302,
    "positive_pct": 3.6,
    "negative_pct": 0.5,
    "neutral_pct": 95.9,
    "avg_polarity": 0.014
}
```

### Payload completo da API `/api/scrape`
```python
{
    "summary": {...},              # agregado de todos os vídeos
    "top_comments_by_likes": [...],
    "top_comments_by_replies": [...],
    "top_words": [{"word": str, "count": int}, ...],
    "wordcloud_path": "static/wordcloud.png",
    "sentiment_distribution": {"positive": 3.6, "negative": 0.5, "neutral": 95.9},
    "per_video": [{"url", "video_info", "summary"}, ...],
    "total_videos": 1,
    "successful_scrapes": 1,
    "video_stats": dict | list,    # single = dict, multiple = list
    "scraped_at": "ISO datetime",
    "urls_scraped": ["..."],
    "raw_results": [...]           # dado bruto por URL
}
```

---

## Estratégias de Extração de Video Stats (cascata)

1. `_try_api_item_detail()` — API `/api/item/detail/?aid=1988` (frequentemente bloqueada)
2. `_try_oembed()` — oEmbed API (só title/author, sem stats numéricas)
3. `_try_html_extraction()` — Parse HTML + aria-labels e data-e2e attributes
4. `_try_embed_v2()` — Embed `https://www.tiktok.com/embed/v2/{video_id}` (mais confiável)

**Condição atual:** embed_v2 só roda se `likes` ou `plays` estiver ausente. Isso faz `favorites` (collectCount) ficar vazio quando as outras estratégias acham likes/plays mas não coletam favorites.

---

## Bugs (resolvidos em 2026-06-02)

### ✅ BUG-1: Label "Comentários" ambíguo — RESOLVIDO
- `summary.total_comments` (scrapeados) → label "Comentarios Analisados"
- `video_stats.comments` (total TikTok) → label "Total no TikTok"
- index.html linhas dos stat-labels/video-stat-labels renomeadas.

### ⚠️ BUG-2: Favoritos (collectCount) — CÓDIGO CORRIGIDO, dado limitado pela fonte
- `_try_embed_v2` agora roda também quando `favorites` está ausente (scraper.py).
- **Limitação:** os endpoints públicos do TikTok (item/detail, HTML, embed v2) atualmente
  NÃO expõem `collectCount` de forma confiável → `favorites` pode permanecer ausente.
  Quando o endpoint retorna, o campo popula. Frontend e engagement degradam graciosamente
  (campo ausente → card oculto; numerador do engagement usa 0).

### ✅ BUG-3: Título + @creator — RESOLVIDO
- `author_unique_id` agora tem fallback do username da URL (scraper.py).
- Card de header full-width (`renderVideoHeaderCard`) com título + @handle + chips.

### ✅ BUG-4: parse_count — RESOLVIDO
- Reescrito: detecta sufixo de escala (K/M/B/mil) ANTES de remover pontos.
  Suporta PT-BR ("13.600.000") e EN ("14.4K"). 10/10 casos de teste OK.

### ✅ BUG-5: Filtragem multi-vídeo — RESOLVIDO
- Scope-bar (`renderComparisonBlock`/`applyScope`): filtra o dashboard por vídeo
  específico ou por criador (@username); tabela de comparação com ranking por APS.

---

## Análise de Sentimento

- **Motor:** palavras-chave PT (`POSITIVE_PT`, `NEGATIVE_PT` ≈ 60 palavras cada) + TextBlob EN
- **Pesos:** 70% PT + 30% EN (se detectado PT), inverso caso contrário
- **Threshold:** polarity > 0.15 = positivo, < -0.15 = negativo, else neutro
- **Limitação:** ~96% neutro é esperado — comentários curtos/emojis/outros idiomas não ativam keywords
- **langdetect** instalado → detecção de idioma por comentário (PT/EN/ES) em `insights.language_breakdown`;
  fallback de heurística de stopwords quando ausente.
- **Melhoria futura:** o motor de sentimento ainda é keyword+TextBlob (PT/EN); RU/ZH não cobertos.

---

## Features — IMPLEMENTADAS (análise de PERFORMANCE do post)

> Foco: o post analisado já é uma **publicidade veiculada** (ex.: Sephora). A análise mede
> o **desempenho do post**, não potencial de compra de mídia.

Todas em `insights.py` (backend) + `templates/index.html` (UI). Ver `IMPLEMENTATION_PLAN.md`.

1. ✅ **Video header card** — título, @creator, chips (views/curtidas/link)
2. ✅ **Engagement Rate** — (likes+comments+shares+favorites) / plays × 100 + tier (baixo/bom/excelente)
3. ✅ **Purchase Intent Detector** — % comentários com sinais de compra (PT/EN/ES) + exemplos
4. ✅ **Brand Safety Score** — 0–100 (negativos, toxicidade, spam, diversidade de autores)
5. ✅ **Topic Clusters** — 6 temas por keywords (Música, Produto/Marca, Humor, Emoção, Pergunta/CTA, Spam)
6. ✅ **Language Breakdown** — distribuição PT/EN/ES/outros (langdetect)
7. ✅ **Multi-video filter** — filtra dashboard por vídeo ou criador + tabela de comparação (ranking por performance)
8. ✅ **Post Performance Score** — composto 0–100 (eng 0.30, sentimento 0.25, intenção 0.20, alcance 0.15, brand 0.10) + justificativa de desempenho PT-BR
9. ✅ **Export PDF/CSV** — relatório executivo (fpdf2) e CSV de comentários; + session manager
10. ✅ **Thread Analyzer** — top comentários por respostas (expansível quando o backend enviar replies)
11. ✅ **Coleta total de comentários** (It2) — sem cap; job em background com progresso ao vivo
12. ✅ **Word cloud interativa** (It2) — tamanho ∝ frequência, cor por sentimento, filtros Todas/Positivas/Negativas/Neutras

**Ideias futuras:** preservar replies pai→filho no scraper p/ thread analyzer expandir de verdade;
sentimento por idioma; thumbnail real do vídeo; comparação histórica entre sessões; persistir jobs
fora da memória (Redis) para multi-worker.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Dashboard (verifica cache) |
| POST | `/api/scrape` | **Inicia job em background** `{"urls": "url1\nurl2"}` → `{job_id}` (202) |
| GET | `/api/scrape/status?job_id=` | Status do job (polling) — `running`/`done`/`error` + `progress` |
| GET | `/api/results` | Retorna cache JSON (ou sessão via `?session=<id>`) |
| GET | `/api/clear` | Limpa cache |
| GET | `/api/mock` | Retorna dados mock (teste) |
| GET | `/api/sessions` | Lista sessões salvas |
| POST | `/api/sessions/save` | Salva análise atual `{"name": "..."}` |
| GET | `/api/export/csv` | Exporta comentários CSV (`?vid=`, `?session=`) |
| GET | `/api/export/pdf` | Relatório PDF executivo (`?vid=`, `?session=`) |

**Scraping = job em background (Iteração 2):** scrapes grandes (milhares de comentários) não cabem
num request síncrono. `POST /api/scrape` retorna `job_id` na hora; o front faz polling em
`/api/scrape/status` mostrando a contagem ao vivo. `JOBS` é um dict em memória (single-process).
O scraper coleta TODOS os comentários (sem cap de páginas; teto de segurança 2000) avançando pelo
cursor da API; `count=50` por página; sleeps 1.0s (top) / 0.5s (replies).

**Insights no payload (de insights.py, via analyzer):** `engagement {rate_pct,tier,tier_label,components}`,
`purchase_intent {intent_pct,intent_count,examples}`, `language_breakdown {distribution,dominant,counts}`,
`topic_clusters {clusters[{name,count,pct}]}`, `brand_safety {score,tier,breakdown}`,
`post_performance {score,tier,justification,components,contributions}` (desempenho do post — o post É a publi),
`wordcloud_data [{word,count,sentiment,polarity}]` (nuvem interativa com filtros). Cada item de `per_video`
carrega esses campos + `vid`; há também `creators` (agregado por @username). **Shapes do backend são
canônicos** — o frontend lê exatamente essas chaves.

---

## Contexto de Uso

- **Usuário primário:** CMO ou equipe de mídia de um anunciante avaliando se vale investir em publicidade no vídeo/criador
- **Caso de uso:** colar URL de vídeo viral → entender engajamento real, qualidade da audiência, intenção de compra, segurança de marca
- **Múltiplos vídeos:** comparar vídeos do mesmo criador ou criadores diferentes
- **Idioma:** interface PT-BR, comentários multilingues (PT, EN, ES, RU comuns)
- **Limitação de scraping:** TikTok pode bloquear após muitas requisições; fallback para mock garante demo funcional

---

## Variáveis de Ambiente / Config

Nenhuma variável obrigatória. Tudo configurado em código:
- Porta Flask: 5000 (app.py linha 186)
- Timeout scraping: 600s (app.py linha 117)
- Max páginas comentários: 50 páginas × 30 = 1.500 top-level (scraper.py linha 327)
- Max páginas replies: 20 páginas × 30 = 600 replies por comentário (scraper.py linha 403)
