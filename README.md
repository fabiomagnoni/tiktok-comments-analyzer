# TikTok Comments Analyzer

Dashboard completo para scraping e análise de comentários do TikTok com suporte a múltiplas URLs.

## Funcionalidades

- 🎬 **Scraping real** via API web do TikTok (sem Playwright necessário)
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

# Baixar dados do NLTK (primeira execução)
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords')"
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
├── scraper.py          # Scraper via API web do TikTok
├── analyzer.py         # Análise de sentimento + Word Cloud
├── mock_data.py        # Dados mock para fallback/teste
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

O scraper usa a **API web do TikTok** diretamente:

1. **Obtenção de cookies** - visita tiktok.com para obter sessão válida
2. **Extração do video ID** - parse da URL para obter o ID do vídeo
3. **Chamada à API** - endpoint `/api/comment/list/online/` com paginação
4. **Fallback** - se a API falhar, usa dados mock para teste

## API Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Dashboard principal |
| `/api/scrape` | POST | Scraping de múltiplas URLs `{ "urls": "url1\nurl2" }` |
| `/api/results` | GET | Retorna dados cacheados |
| `/api/clear` | GET | Limpa dados cacheados |
| `/api/mock` | GET | Dados mock para teste rápido |
