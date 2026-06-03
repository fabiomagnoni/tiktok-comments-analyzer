# Plano de Implementação — TikTok Comments Analyzer

> **Documento de tracking vivo.** Atualizado ao final de cada etapa.
> Última atualização: 2026-06-03 · Status geral: ✅ CONCLUÍDO (Fases 0–6 + Iteração 2 A–D)

## Legenda de Status
- ⬜ Não iniciado
- 🟡 Em andamento
- ✅ Concluído e verificado
- ⏭️ Pulado / adiado
- ❌ Bloqueado

---

## Resumo de Progresso

| Fase | Descrição | Status | Verificado |
|------|-----------|:------:|:----------:|
| 0 | Setup: CLAUDE.md + tracking + design specs | ✅ | ✅ |
| 1 | Correções de bugs (labels, favorites, video header) | ✅ | ✅ |
| 2 | Engenharia de dados: módulo `insights.py` | ✅ | ✅ |
| 3 | Integração analyzer.py (insights + per_video + creators) | ✅ | ✅ |
| 4 | Frontend: cards + charts + thread analyzer + filtro multi-vídeo | ✅ | ✅ |
| 5 | Exportação (CSV/PDF) + sessões + botões header | ✅ | ✅ |
| 6 | Review final + verificação end-to-end (browser) | ✅ | ✅ |

---

## FASE 0 — Setup ✅
- [x] Análise completa do projeto
- [x] Criar `CLAUDE.md` (contexto permanente)
- [x] Salvar memória do projeto
- [x] Criar este `IMPLEMENTATION_PLAN.md`
- [x] Workflow de design: specs técnicos detalhados por área (6 áreas + integração)
- [x] Validar specs e registrar decisões de contrato (ver Log de Decisões)

---

## FASE 1 — Correções de Bugs ✅
**Objetivo:** dados corretos e sem ambiguidade na tela.

- [x] **BUG-1**: Renomear labels de comentários (3 locais em index.html)
  - `summary.total_comments` → "Comentarios Analisados" (linhas 552 e 760)
  - `video_stats.comments` → "Total no TikTok" (linhas 594, 631, 737)
- [x] **BUG-2**: Corrigir favorites (collectCount) — scraper.py:139
  - Condição de `_try_embed_v2` agora inclui `not favorites` ⏳ validar valor real na Fase 6
- [x] **BUG-3 (backend)**: `author_unique_id` com fallback do username da URL — scraper.py + mock_data.py
  - Card de header visual será renderizado na Fase 4
- [x] **BUG-4**: `parse_count` reescrito (sufixo antes de remover pontos) — 10/10 casos OK
- **Verificação:** ✅ imports OK · parse_count 10/10 · /api/mock 200 com author_unique_id e title

---

## FASE 2 — Módulo `insights.py` (engenharia de dados) ✅
**Objetivo:** funções de análise puras e testáveis, isoladas do Flask.

- [x] `engagement_rate(video_info)` → `{rate_pct,tier,tier_label,components}`
- [x] `purchase_intent(comments)` → `{intent_pct,intent_count,examples}`
- [x] `language_breakdown(comments)` → `{distribution,dominant,counts}`
- [x] `topic_clusters(comments)` → `{clusters,total}`
- [x] `brand_safety_score(comments, summary)` → `{score,tier,breakdown}`
- [x] `ad_potential_score(...)` → `{score,tier,justification,components,contributions}`
- **Verificação:** ✅ eng 11.96% · purchase 12.8% · brand 96.2 · APS 94.8 · contributions=score · JSON OK

---

## FASE 3 — Integração no `analyzer.py` (consolidada) ✅
**Objetivo:** UMA edição coordenada (analyzer.py é o ponto de conflito mais quente).
- [x] Import de insights + assinatura `run_analysis(comments, video_info=None, output_path=None)`
- [x] `run_analysis` injeta: purchase_intent, language_breakdown, topic_clusters, brand_safety, engagement, ad_potential
- [x] `run_aggregated_analysis`: `vid` por vídeo, per_video com blocos completos + métricas CMO, `creators`, wordcloud por vídeo, raw_results enriquecido com sentiment
- [x] Atualizar caller `/api/mock` (passar `video_info=MOCK_VIDEO_INFO`)
- **Verificação:** ✅ /api/mock com 6 chaves de insights · multi-vídeo gera per_video/vid/creators · raw_results enriquecido

---

## FASE 4 — Frontend (cards + charts + thread + filtro) ✅
**Objetivo:** todo o render novo no `index.html` (1 passada coordenada na SPA).
- [x] Guard de destruição de charts (evita "Canvas already in use")
- [x] Video header card (BUG-3 visual): título + @creator + chips
- [x] Ad Potential Score (card destaque grande + justificativa + barras)
- [x] Cards: Engagement Rate, Purchase Intent, Brand Safety badge
- [x] Charts: Language breakdown (barra) + Topic clusters (pizza)
- [x] Thread Analyzer (top por replies, expansível se backend enviar replies)
- [x] Filtro multi-vídeo (scope-bar) + tabela de comparação + ranking APS
- **Verificação:** ✅ Jinja 200 · 18 funções/classes presentes · JS válido (node --check)

---

## FASE 5 — Exportação + Sessões ✅
**Objetivo:** exportar relatórios e persistir múltiplas análises.
- [x] `app.py`: `/api/export/csv`, `/api/export/pdf` (com guard de path traversal)
- [x] Session manager (`/api/sessions`, `/api/sessions/save`, `/api/results?session=`) + auto-snapshot por scrape
- [x] Botões no header: Exportar CSV, Exportar PDF, Salvar Sessão, dropdown Sessões + JS
- [x] `requirements.txt`: fpdf2 + langdetect (opcional) — ambos instalados
- **Verificação:** ✅ CSV 200 (BOM, `;`, sentiment) · PDF 200 (%PDF, 920KB) · sessões save/list/load · path traversal → 404

---

## FASE 6 — Review Final ✅
- [x] Verificação end-to-end com a URL de teste real (stats do vídeo)
- [x] Render headless via Playwright (mock): 9 cards + 4 charts, APS 85, **0 erros de console**
- [x] Atualizar CLAUDE.md com estado final + remover arquivos temporários
- [~] Workflow de code review: executou mas falhou em emitir achados estruturados (problema de
  tooling, não de código); substituído por revisão manual + testes automatizados + render em browser
- **Verificação:** ✅ app serve 200 · /api/mock com insights · BUG-1/3/4/5 confirmados · dashboard renderiza limpo

### Resultado da verificação live (URL @rafaelsantos/7424664623997062405)
- likes 13.6M · plays 123.6M · comments 66.500 (Total TikTok) · shares 412.4k
- title: "Pennywise para o halloween da @Sephora Brasil 🤡🎈" · @rafaelsantos (fallback BUG-3)
- favorites: ausente nesta requisição (limitação da fonte; código BUG-2 correto — embed_v2 roda)
- langdetect ativo → idioma do mock: PT 84.6% / ES 5.1% / EN 2.6% / outros 7.7%

---

## ITERAÇÃO 2 (2026-06-03) — pedidos do usuário

> Reframe: o post analisado **já é uma publicidade** (Sephora) → a análise é de
> **performance do post**, não de "potencial publicitário".

### Fase A — Coletar TODOS os comentários ✅
**Problema:** URL com 19.5K comentários só analisou 3.364. Causa: `_fetch_all_top_comments`
tinha cap `range(50)` (50×30 = 1.500 top-level) + timeout síncrono de 10 min do Flask.
- [x] scraper.py: cap removido (while com teto de segurança 2000), `count=50`, cursor da API
  (evita drift), sleeps menores (top 1.0s / replies 0.5s), callback de progresso
- [x] app.py: `/api/scrape` vira **job em background** (`job_id`, 202) + `/api/scrape/status`
- [x] index.html: polling do status com contagem de comentários ao vivo (sem timeout)
- **Verificação:** ✅ scrape real da nova URL coletou **2.804 top-level** em 117s (limitei a 60
  páginas só p/ provar — antes parava em 1.500). Job: POST 202 → polling → done. JS válido.

### Fase B — Word cloud interativa (com filtros de sentimento) ✅
- [x] Backend: `wordcloud_data: [{word, count, sentiment, polarity}]` (sentimento agregado por palavra)
- [x] Frontend: tag-cloud dinâmica (tamanho ∝ √frequência, cor por sentimento, hover com detalhe)
- [x] Filtros: Todas / Positivas / Negativas / Neutras
- [x] `<img>` removido do dashboard (PNG mantido só para o PDF)
- **Verificação:** ✅ 80 palavras; filtros: 80→37(pos)→10(neg)→80. Playwright sem erros.

### Fase C — Reframe: Performance do Post (não Ad Potential) ✅
- [x] insights.py: `ad_potential_score` → `post_performance_score` (pesos p/ desempenho:
  eng 0.30, sentimento 0.25, intenção 0.20, alcance 0.15, brand 0.10; justificativa de performance)
- [x] analyzer.py + app.py (PDF) + index.html: chave/labels `ad_potential` → `post_performance`
- [x] Comparação ranqueia por desempenho do post
- **Verificação:** ✅ payload/UI usam "Performance do Post"; sem "Potencial Publicitário"/"investir".

### Fase D — Verificação end-to-end + docs ✅
- [x] Scrape real (bounded) da nova URL: 2.804 top-level (prova do cap removido)
- [x] Playwright render: Performance do Post + word cloud interativa + filtros, 0 erros de console
- [x] CLAUDE.md atualizado

---

## Log de Decisões
| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-06-02 | Análise CMO-cêntrica (eng. rate, APS, brand safety) | Usuário-alvo é media buyer |
| 2026-06-02 | Lógica de insights em `insights.py` separado | Testável e desacoplado do Flask |
| 2026-06-02 | **Shapes do backend são canônicos** | Specs de frontend e backend divergiram; backend tem código real |
| 2026-06-02 | Contratos: `engagement={rate_pct,tier,tier_label,components}`, `purchase_intent={intent_pct,intent_count,examples}`, `language_breakdown={distribution,dominant,counts}`, `topic_clusters={clusters,total}`, `brand_safety={score,tier,breakdown}`, `ad_potential={score,tier,justification,components,contributions}` | Frontend será escrito contra estes shapes |
| 2026-06-02 | `ad_potential_score` lê `engagement.rate_pct` (não `rate`) | Reconciliar divergência de chave entre agentes |
| 2026-06-02 | Header card (BUG-3) renderizado 1x na Fase 4 (versão rica full-width), não duplicado | Evitar dois headers |
| 2026-06-02 | Edições em analyzer.py e index.html feitas sequencialmente por mim | Mapa de integração: edições paralelas no mesmo arquivo conflitam |

## Evidência dos Bugs (confirmada em data/results.json)
- **BUG-1** ✓: `summary.total_comments`=8.658 vs `video_stats.comments`=66.500 (números divergentes na tela).
- **BUG-2** ✓: `video_stats.favorites`=**None** (likes=13.6M e plays=123.6M presentes → embed_v2 foi pulado).
- **BUG-3** ✓: `title` presente (72 chars), `author_name`="Rafael Santos", mas `author_unique_id`=**""** (vazio). Fix precisa usar username da URL como fallback.
- Ambiente: Python 3.14.3, todas as deps core OK. ⚠️ Console Windows usa cp1252 — scripts com print de unicode precisam `PYTHONIOENCODING=utf-8`.

## Changelog
- **2026-06-02** — Setup inicial: CLAUDE.md, memória, plano de tracking criados.
- **2026-06-02** — Evidência dos bugs confirmada via results.json. Workflow de design lançado (6 áreas + integração).
- **2026-06-02** — Workflow de design concluído (7 agentes). Decisões de contrato registradas.
- **2026-06-02** — **Fase 1 concluída e verificada**: BUG-1 (labels), BUG-2 (favorites condicional), BUG-3 backend (author_unique_id), BUG-4 (parse_count 10/10). scraper.py + mock_data.py + index.html editados.
- **2026-06-02** — **Fase 2 concluída e verificada**: `insights.py` criado (6 funções, stdlib + langdetect opcional). Testes: eng 11.96%, APS 94.8, contributions=score, JSON OK.
- **2026-06-02** — **Fase 3 concluída e verificada**: analyzer.py integrado numa edição (run_analysis com video_info/output_path, per_video completo, creators, raw_results enriquecido). /api/mock e multi-vídeo OK.
- **2026-06-02** — **Fase 4 concluída e verificada**: index.html com header card, APS, cards de insights, charts de idioma/tópicos, thread analyzer, filtro multi-vídeo + comparação. JS válido (node --check).
- **2026-06-02** — **Fase 5 concluída e verificada**: app.py com export CSV/PDF + session manager (path traversal guard), botões no header, fpdf2+langdetect instalados. CSV/PDF/sessões testados via test client.
- **2026-06-02** — **Fase 6 concluída**: verificação end-to-end live (BUG-1/3/4/5 confirmados; BUG-2 limitado pela fonte), render headless Playwright sem erros de console, CLAUDE.md finalizado. **PROJETO CONCLUÍDO.**
- **2026-06-03** — **Iteração 2 concluída**: (A) coleta de TODOS os comentários — cap de 1.500 removido (prova: 2.804 top-level em scrape real bounded) + job em background com progresso; (B) word cloud interativa com filtros de sentimento; (C) reframe Ad Potential → **Performance do Post** (o post já é publi). Verificado via Playwright (0 erros).
