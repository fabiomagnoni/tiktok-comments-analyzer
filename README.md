# TikTok Comments Analyzer

Dashboard completo para scraping e análise de comentários do TikTok com suporte a múltiplas URLs.

## Funcionalidades

- 🎬 **Scraping real** via Playwright (contorna WAF do TikTok)
- 🔗 **Múltiplas URLs** - insira 1 ou N vídeos para analisar
- ❤️ **Engajamento** - likes, comentários e respostas por comentário
- 📊 **Análise de sentimento** - positivo, negativo, neutro (português + inglês)
- ☁️ **Word Cloud** - nuvem de palavras gerada automaticamente
- 💾 **Persistência local** - dados salvos em JSON para reutilização
- 📱 **Por vídeo** - análise individual quando múltiplas URLs são fornecidas

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/fabiomagnoni/tiktok-comments-analyzer.git
cd tiktok-comments-analyzer

# Criar ambiente virtual (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# ou: source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Instalar Playwright browsers (chromium)
playwright install chromium
```

## Uso

```bash
python app.py
```

Acesse: **http://localhost:5000**

### Como usar o dashboard

1. Cole uma ou mais URLs de vídeos TikTok no campo de texto (uma por linha)
2. Clique em **"Analisar"** para fazer scraping real
3. Os dados são salvos automaticamente em `data/results.json`
4. Na próxima vez, clique em **"Carregar Cache"** para ver os dados sem re-scraping

## Estrutura do Projeto

```
tiktok-comments-analyzer/
├── app.py              # Flask backend (API + servidor)
├── scraper.py          # Playwright scraper com anti-detecção
├── analyzer.py         # Análise de sentimento + Word Cloud
├── requirements.txt    # Dependências Python
├── .gitignore
├── data/               # Dados persistidos em JSON (auto-criado)
│   └── results.json
├── static/             # Imagens geradas (word cloud, etc.)
│   └── wordcloud.png
└── templates/
    └── index.html      # Dashboard SPA com Chart.js
```

## Como funciona o scraping

O TikTok usa um WAF (Web Application Firewall) chamado SlardarWAF que bloqueia requisições HTTP diretas. O scraper resolve isso usando:

1. **Playwright** - navegador Chromium real, não requisição HTTP
2. **Anti-detecção** - remove propriedades de automação do navigator
3. **Scroll automático** - carrega comentários via lazy loading
4. **Timeouts generosos** - aguarda carregamento completo da página

## API Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Dashboard principal |
| `/api/scrape` | POST | Scraping de múltiplas URLs `{ "urls": "url1\nurl2" }` |
| `/api/results` | GET | Retorna dados cacheados |
| `/api/clear` | GET | Limpa dados cacheados |
