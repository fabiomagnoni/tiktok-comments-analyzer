"""
Flask App - Backend API para o Dashboard de Análise de Comentários TikTok
"""
import os
import json
import asyncio
import threading
from flask import Flask, render_template, jsonify, request

from scraper import scrape_tiktok
from analyzer import run_analysis

app = Flask(__name__, template_folder='templates', static_folder='static')

# Cache para evitar re-scraping desnecessário
cache = {}

TIKTOK_URLS = [
    'https://www.tiktok.com/@ricaperrone/video/7645152910459915541',
]


@app.route('/')
def index():
    """Página principal do dashboard."""
    return render_template('index.html')


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Endpoint para iniciar o scraping e análise."""
    data = request.get_json() or {}
    url = data.get('url', TIKTOK_URLS[0])

    if url in cache:
        return jsonify({'status': 'success', 'data': cache[url], 'cached': True})

    try:
        result = {'comments': [], 'video_info': {}}

        def do_scrape():
            nonlocal result
            comments, video_info = asyncio.run(scrape_tiktok(url, headless=True))
            result['comments'] = comments or []
            result['video_info'] = video_info or {}

        thread = threading.Thread(target=do_scrape)
        thread.start()
        thread.join(timeout=120)  # Timeout de 2 minutos

        # Se não conseguiu extrair comentários, usa dados mock como fallback
        if not result['comments']:
            app.logger.warning("Scraping falhou, usando dados mock")
            try:
                from mock_data import MOCK_COMMENTS, MOCK_VIDEO_INFO
                result['comments'] = MOCK_COMMENTS
                result['video_info'] = MOCK_VIDEO_INFO
            except ImportError:
                return jsonify({
                    'status': 'error',
                    'message': 'Não foi possível extrair comentários e dados mock não disponíveis.',
                })

        # Executa análise
        analysis = run_analysis(result['comments'])
        analysis['video_info'] = result.get('video_info', {})

        # Salva no cache
        cache[url] = analysis

        return jsonify({'status': 'success', 'data': analysis, 'cached': False})

    except Exception as e:
        import traceback
        error_msg = f"Erro: {str(e)}\n{traceback.format_exc()}"
        app.logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': str(e),
        }), 500


@app.route('/api/mock')
def api_mock():
    """Endpoint para testar com dados mock (sem scraping)."""
    try:
        from mock_data import MOCK_COMMENTS, MOCK_VIDEO_INFO
        analysis = run_analysis(MOCK_COMMENTS)
        analysis['video_info'] = MOCK_VIDEO_INFO
        return jsonify({'status': 'success', 'data': analysis, 'cached': False})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/status')
def api_status():
    """Endpoint de status."""
    return jsonify({
        'status': 'ok',
        'cached_urls': list(cache.keys()),
    })


if __name__ == '__main__':
    print("=" * 60)
    print("  🎬 TikTok Comments Analyzer")
    print("  Dashboard: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
