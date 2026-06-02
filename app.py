"""
Flask App - Backend para Dashboard de Análise de Comentários TikTok
Suporte a múltiplas URLs com scraping real via Playwright.
Dados persistidos em JSON local para reutilização.
Fallback garantido para dados mock quando o scraping falha.
"""
import os
import json
import asyncio
import threading
from datetime import datetime

from flask import Flask, render_template, jsonify, request

from scraper import scrape_multiple_urls
from analyzer import run_aggregated_analysis

app = Flask(__name__, template_folder='templates', static_folder='static')

# Caminho para persistência de dados
DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data'
)
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs('static', exist_ok=True)  # Para a wordcloud image


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


@app.route('/')
def index():
    """Página principal do dashboard."""
    cached = load_cached_results()
    return render_template('index.html', has_cache=cached is not None)


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Endpoint para scraping de múltiplas URLs com análise agregada."""
    data = request.get_json() or {}
    urls_raw = data.get('urls', '')

    # Parse das URLs (uma por linha ou separadas por vírgula)
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
            'message': 'Formato de URLs inválido'
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

    def do_work():
        nonlocal result
        try:
            # Scraping de todas as URLs (fallback para mock garantido)
            scrape_results = asyncio.run(scrape_multiple_urls(unique_urls))

            # Análise agregada
            analysis = run_aggregated_analysis(scrape_results)

            # Adiciona metadados
            analysis['scraped_at'] = datetime.now().isoformat()
            analysis['urls_scraped'] = unique_urls
            analysis['raw_results'] = scrape_results

            result = {'status': 'success', 'data': analysis}

            # Persiste no disco
            save_results(analysis)

        except Exception as e:
            import traceback
            error_msg = f"Erro: {str(e)}\n{traceback.format_exc()}"
            app.logger.error(error_msg)
            result = {'status': 'error', 'message': str(e)}

    result = None
    thread = threading.Thread(target=do_work, daemon=True)
    thread.start()
    thread.join(timeout=600)  # Timeout de 10 minutos para múltiplas URLs

    if result is None:
        return jsonify({
            'status': 'error',
            'message': (
                'Timeout: o scraping demorou mais do que o esperado. '
                'Tente novamente ou use dados mock.'
            ),
        }), 504

    return jsonify(result)


@app.route('/api/results')
def api_results():
    """Retorna os últimos resultados cacheados."""
    cached = load_cached_results()
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

    analysis = run_analysis(MOCK_COMMENTS)
    analysis['scraped_at'] = datetime.now().isoformat()
    analysis['urls_scraped'] = [
        'https://www.tiktok.com/@ricaperrone/video/7645152910459915541'
    ]

    return jsonify({'status': 'success', 'data': analysis})


if __name__ == '__main__':
    print("=" * 60)
    print("  🎬 TikTok Comments Analyzer")
    print("  Dashboard: http://localhost:5000")
    print("=" * 60)

    # Verifica se há dados cacheados
    cached = load_cached_results()
    if cached:
        print(
            f"\n  ℹ️  Dados cacheados encontrados "
            f"({cached.get('total_comments', 0)} comentários)"
        )
        print("     Use /api/clear para limpar e fazer novo scraping")

    app.run(debug=True, host='0.0.0.0', port=5000)
