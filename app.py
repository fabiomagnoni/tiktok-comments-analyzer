"""
Flask App - Backend para Dashboard de Analise de Comentarios TikTok
Suporte a multiplas URLs com scraping real via API web.
Dados persistidos em JSON local para reutilizacao.
Fallback garantido para dados mock quando o scraping falha.
"""
import os
import io
import csv
import re
import json
import uuid
import threading
import unicodedata
from datetime import datetime

from flask import Flask, render_template, jsonify, request, Response

from scraper import scrape_multiple_urls
from analyzer import run_aggregated_analysis

app = Flask(__name__, template_folder='templates', static_folder='static')

# Caminho para persistencia de dados
DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data'
)
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs('static', exist_ok=True)  # Para a wordcloud image

# Jobs de scraping em background (job_id -> estado). Em memória (single-process).
JOBS = {}


def load_cached_results():
    """Carrega resultados cacheados do arquivo JSON."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_results(data):
    """Salva resultados no arquivo JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# Session manager (salvar/listar/carregar múltiplas análises)
# ============================================================
def slugify(name):
    """Normaliza um nome para uso seguro em nome de arquivo."""
    nfkd = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-zA-Z0-9]+', '-', nfkd).strip('-').lower()
    return s[:40] or 'sessao'


def list_sessions():
    """Lê o índice de sessões salvas (lista de metadados)."""
    path = os.path.join(SESSIONS_DIR, 'index.json')
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_session(data, name=None):
    """Salva um snapshot da análise em data/sessions/ e atualiza o índice."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    ts = datetime.now()
    sid = ts.strftime('%Y%m%d_%H%M%S')
    base = name or (data.get('urls_scraped') or ['sessao'])[0]
    fname = f'{sid}_{slugify(base)}.json'
    with open(os.path.join(SESSIONS_DIR, fname), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    creators = sorted({(v.get('video_info') or {}).get('author_unique_id', '')
                       for v in data.get('per_video', [])
                       if (v.get('video_info') or {}).get('author_unique_id')})
    meta = {
        'id': fname[:-5], 'file': fname, 'name': name or slugify(base),
        'saved_at': ts.isoformat(),
        'total_videos': data.get('total_videos', 1),
        'total_comments': data.get('summary', {}).get('total_comments', 0),
        'creators': creators,
    }
    index = list_sessions()
    index.insert(0, meta)
    index = index[:50]
    with open(os.path.join(SESSIONS_DIR, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return meta


def load_session(session_id):
    """Carrega uma sessão pelo id, com proteção contra path traversal."""
    if not session_id or '..' in session_id or '/' in session_id or '\\' in session_id:
        return None
    abspath = os.path.abspath(os.path.join(SESSIONS_DIR, session_id + '.json'))
    if not abspath.startswith(os.path.abspath(SESSIONS_DIR) + os.sep):
        return None
    if not os.path.exists(abspath):
        return None
    try:
        with open(abspath, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _resolve_export_data(req):
    """Resolve (data, scope) a exportar a partir de ?session= e ?vid=."""
    session = req.args.get('session')
    data = load_session(session) if session else load_cached_results()
    if not data:
        raise ValueError('Nenhum dado para exportar. Faça um scraping primeiro.')
    vid = req.args.get('vid')
    scope = None
    if vid:
        scope = next((v for v in data.get('per_video', [])
                      if str(v.get('vid')) == str(vid)), None)
    return data, scope


def _fmt_num(n):
    """Formata número grande de forma compacta para tabelas do PDF."""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return '-'
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n/1_000:.1f}k'
    return str(n)


@app.route('/')
def index():
    """Pagina principal do dashboard."""
    cached = load_cached_results()
    return render_template('index.html', has_cache=cached is not None)


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Endpoint para scraping de multiplas URLs com analise agregada."""
    data = request.get_json() or {}
    urls_raw = data.get('urls', '')

    # Parse das URLs (uma por linha ou separadas por virgula)
    if isinstance(urls_raw, str):
        urls = [
            u.strip()
            for u in urls_raw.replace(',', '\n').split('\n')
            if u.strip()
        ]
    elif isinstance(urls_raw, list):
        urls = [u.strip() for u in urls_raw if u.strip()]
    else:
        return jsonify({
            'status': 'error',
            'message': 'Formato de URLs invalido'
        }), 400

    if not urls:
        return jsonify({
            'status': 'error',
            'message': 'Nenhuma URL fornecida'
        }), 400

    # Remove duplicatas mantendo ordem
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    # Job em background: scrapes longos (milhares de comentarios) nao cabem em
    # um request sincrono. Retornamos um job_id e o front faz polling do status.
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        'status': 'running',
        'progress': {'stage': 'iniciando', 'total_collected': 0,
                     'video_index': 0, 'total_videos': len(unique_urls)},
        'data': None, 'error': None,
        'started_at': datetime.now().isoformat(),
    }

    def do_work():
        try:
            def on_progress(info):
                JOBS[job_id]['progress'] = info

            scrape_results = scrape_multiple_urls(unique_urls, progress_cb=on_progress)

            JOBS[job_id]['progress'] = {'stage': 'analisando',
                                        'total_collected': sum(len(r.get('comments', []))
                                                               for r in scrape_results)}
            analysis = run_aggregated_analysis(scrape_results)
            analysis['scraped_at'] = datetime.now().isoformat()
            analysis['urls_scraped'] = unique_urls
            analysis['raw_results'] = scrape_results

            save_results(analysis)
            try:
                save_session(analysis)
            except Exception:
                pass

            JOBS[job_id]['data'] = analysis
            JOBS[job_id]['status'] = 'done'
        except Exception as e:
            import traceback
            app.logger.error(f"Erro: {e}\n{traceback.format_exc()}")
            JOBS[job_id]['error'] = str(e)
            JOBS[job_id]['status'] = 'error'

    threading.Thread(target=do_work, daemon=True).start()
    return jsonify({'status': 'started', 'job_id': job_id}), 202


@app.route('/api/scrape/status')
def api_scrape_status():
    """Status de um job de scraping (polling). Retorna data quando concluido."""
    job_id = request.args.get('job_id', '')
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'status': 'error', 'message': 'Job não encontrado'}), 404
    resp = {'status': job['status'], 'progress': job['progress']}
    if job['status'] == 'done':
        resp['data'] = job['data']
    elif job['status'] == 'error':
        resp['message'] = job['error']
    return jsonify(resp)


@app.route('/api/results')
def api_results():
    """Retorna os últimos resultados cacheados (ou uma sessão salva via ?session=)."""
    session = request.args.get('session')
    cached = load_session(session) if session else load_cached_results()
    if cached:
        return jsonify({'status': 'success', 'data': cached})
    return jsonify({
        'status': 'error',
        'message': (
            'Nenhum resultado encontrado. Execute o scraping primeiro '
            'ou use /api/mock para dados de teste.'
        ),
    }), 404


@app.route('/api/clear')
def api_clear():
    """Limpa os dados cacheados."""
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    return jsonify({'status': 'success', 'message': 'Dados limpos'})


@app.route('/api/mock')
def api_mock():
    """Retorna dados mock para teste do dashboard sem scraping real."""
    from mock_data import MOCK_COMMENTS, MOCK_VIDEO_INFO
    from analyzer import run_analysis

    analysis = run_analysis(MOCK_COMMENTS, video_info=MOCK_VIDEO_INFO)
    analysis['scraped_at'] = datetime.now().isoformat()
    analysis['urls_scraped'] = [
        'https://www.tiktok.com/@ricaperrone/video/7645152910459915541'
    ]
    # Inclui video_stats para o dashboard mostrar as estatisticas do video
    analysis['video_stats'] = MOCK_VIDEO_INFO

    return jsonify({'status': 'success', 'data': analysis})


@app.route('/api/sessions')
def api_sessions_list():
    """Lista as sessões salvas."""
    return jsonify({'status': 'success', 'sessions': list_sessions()})


@app.route('/api/sessions/save', methods=['POST'])
def api_sessions_save():
    """Salva a análise cacheada atual como uma sessão nomeada."""
    body = request.get_json() or {}
    data = load_cached_results()
    if not data:
        return jsonify({'status': 'error', 'message': 'Nada para salvar'}), 404
    meta = save_session(data, body.get('name'))
    return jsonify({'status': 'success', 'session': meta})


@app.route('/api/export/csv')
def export_csv():
    """Exporta os comentários (com sentiment) em CSV. ?session= e ?vid= opcionais."""
    try:
        data, scope = _resolve_export_data(request)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404

    raw = data.get('raw_results', [])
    if scope:
        sources = [r for r in raw if r.get('url') == scope.get('url')]
    else:
        sources = raw

    output = io.StringIO()
    output.write('﻿')  # BOM para o Excel PT-BR reconhecer UTF-8
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['video_url', 'author', 'text', 'likes',
                     'replies_count', 'date', 'sentiment', 'polarity'])
    for r in sources:
        url = r.get('url', '')
        for c in r.get('comments', []):
            text = (c.get('text', '') or '').replace('\n', ' ').replace('\r', ' ')
            writer.writerow([url, c.get('author', ''), text, c.get('likes', 0),
                             c.get('replies_count', 0), c.get('date', ''),
                             c.get('sentiment', 'neutral'), c.get('polarity', 0)])

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    # BOM (escrito acima) faz o Excel PT-BR reconhecer UTF-8 sem charset extra
    resp = Response(output.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = \
        f'attachment; filename=tiktok_comentarios_{ts}.csv'
    return resp


@app.route('/api/export/pdf')
def export_pdf():
    """Gera um relatório PDF executivo. ?session= e ?vid= opcionais."""
    try:
        data, scope = _resolve_export_data(request)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify({'status': 'error',
                        'message': 'fpdf2 não instalado. Rode: pip install fpdf2'}), 500

    def safe(s):
        # fpdf2 core fonts são latin-1; substitui emojis/cirílico por '?'
        return str(s).encode('latin-1', 'replace').decode('latin-1')

    src = scope or data
    summary = src.get('summary', {}) or data.get('summary', {})
    vinfo = (scope.get('video_info', {}) if scope
             else (data.get('video_stats') if isinstance(data.get('video_stats'), dict) else {}))

    pdf = FPDF(format='A4')
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()

    # Helpers: cada linha volta a margem esquerda (new_x) e desce (new_y),
    # evitando o erro "Not enough horizontal space" do fpdf2.
    def line(txt, h=6):
        pdf.multi_cell(0, h, safe(txt), new_x="LMARGIN", new_y="NEXT")

    def head(txt, size=13, h=8):
        pdf.set_font('Helvetica', 'B', size)
        pdf.multi_cell(0, h, safe(txt), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 10)

    pdf.set_font('Helvetica', 'B', 18)
    line('Relatorio de Analise TikTok', 11)
    pdf.set_font('Helvetica', '', 10)
    line('Gerado em ' + datetime.now().strftime('%d/%m/%Y %H:%M'))

    if vinfo:
        pdf.ln(2)
        head('Video: ' + (vinfo.get('title') or '-')[:90], 12, 7)
        line('Criador: @' + (vinfo.get('author_unique_id')
                             or vinfo.get('author_name') or '-'))

    # Resumo de sentimento
    pdf.ln(2)
    head('Resumo')
    line(f"Comentarios analisados: {summary.get('total_comments', 0)}")
    line(f"Positivos {summary.get('positive_pct', 0)}% / "
         f"Neutros {summary.get('neutral_pct', 0)}% / "
         f"Negativos {summary.get('negative_pct', 0)}%")

    # Métricas de performance do post
    eng = src.get('engagement') or data.get('engagement')
    bs = src.get('brand_safety') or data.get('brand_safety')
    perf = src.get('post_performance') or data.get('post_performance')
    pdf.ln(2)
    head('Metricas de Performance')
    if eng:
        line(f"Taxa de engajamento: {eng.get('rate_pct', '-')}% ({eng.get('tier_label', '-')})")
    if bs:
        line(f"Brand Safety: {bs.get('score', '-')}/100 ({bs.get('tier', '-')})")
    if perf:
        line(f"Performance do Post: {perf.get('score', '-')}/100 ({perf.get('tier', '-')})")
        line(perf.get('justification', ''))

    # Tabela de comparação (multi-vídeo, só no agregado)
    rows = sorted(data.get('per_video', []),
                  key=lambda v: (v.get('post_performance') or {}).get('score', 0), reverse=True)
    if len(rows) > 1 and not scope:
        pdf.ln(2)
        head('Comparacao (ranking por desempenho do post)')
        headers = [('#', 8), ('Criador', 45), ('Views', 28), ('Likes', 28),
                   ('Eng%', 18), ('Perf', 16), ('Brand', 18)]
        pdf.set_font('Helvetica', 'B', 9)
        for h, wd in headers:
            pdf.cell(wd, 7, safe(h), border=1)
        pdf.ln()
        pdf.set_font('Helvetica', '', 9)
        for i, v in enumerate(rows, 1):
            vi = v.get('video_info', {})
            cells = [
                (str(i), 8),
                ('@' + (vi.get('author_unique_id') or '?'), 45),
                (_fmt_num(vi.get('plays')), 28),
                (_fmt_num(vi.get('likes')), 28),
                (str((v.get('engagement') or {}).get('rate_pct', '-')), 18),
                (str((v.get('post_performance') or {}).get('score', '-')), 16),
                (str((v.get('brand_safety') or {}).get('score', '-')), 18),
            ]
            for txt, wd in cells:
                pdf.cell(wd, 7, safe(txt), border=1)
            pdf.ln()

    # Top 10 comentários por likes
    top = src.get('top_comments_by_likes', data.get('top_comments_by_likes', []))[:10]
    if top:
        pdf.ln(2)
        head('Top 10 comentarios por likes')
        pdf.set_font('Helvetica', '', 9)
        for c in top:
            line(f"[{c.get('likes', 0)}] @{c.get('author', '?')}: "
                 f"{(c.get('text', '') or '')[:120]}", 5)

    # Word cloud (se existir)
    wc = src.get('wordcloud_path') or data.get('wordcloud_path')
    if wc and os.path.exists(wc):
        try:
            pdf.ln(2)
            pdf.image(wc, w=170)
        except Exception:
            pass

    out = pdf.output()
    if isinstance(out, str):
        out = out.encode('latin-1')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    resp = Response(bytes(out), mimetype='application/pdf')
    resp.headers['Content-Disposition'] = \
        f'attachment; filename=relatorio_tiktok_{ts}.pdf'
    return resp


if __name__ == '__main__':
    print("=" * 60)
    print("  TikTok Comments Analyzer")
    print("  Dashboard: http://localhost:5000")
    print("=" * 60)

    # Verifica se ha dados cacheados
    cached = load_cached_results()
    if cached:
        print(
            f"\n  Dados cacheados encontrados "
            f"({cached.get('total_comments', 0)} comentarios)"
        )
        print("     Use /api/clear para limpar e fazer novo scraping")

    app.run(debug=True, host='0.0.0.0', port=5000)