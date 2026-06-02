"""
Dados mock para teste do dashboard sem necessidade de scraping real.
Use quando o TikTok bloquear o acesso ou para testes rápidos.
"""

MOCK_COMMENTS = [
    # Comentários positivos
    {"text": "Que vídeo incrível! Amei demais!", "likes": 1520, "replies_count": 45, "author": "maria_silva", "date": "2 dias atrás"},
    {"text": "Top demais! Conteúdo excelente como sempre", "likes": 987, "replies_count": 32, "author": "joao_pereira", "date": "1 dia atrás"},
    {"text": "Maravilhoso! Você é muito talentosa!", "likes": 856, "replies_count": 28, "author": "ana_costa", "date": "3 dias atrás"},
    {"text": "Perfeito! Adorei cada segundo deste vídeo", "likes": 743, "replies_count": 19, "author": "carlos_lima", "date": "2 dias atrás"},
    {"text": "Lindo demais! Que conteúdo maravilhoso!", "likes": 654, "replies_count": 15, "author": "julia_santos", "date": "1 dia atrás"},
    {"text": "Show de bola! Conteúdo sensacional!", "likes": 521, "replies_count": 12, "author": "pedro_oliveira", "date": "4 dias atrás"},
    {"text": "Fantástico! Você é a melhor!", "likes": 498, "replies_count": 10, "author": "fernanda_rocha", "date": "3 dias atrás"},
    {"text": "Incrível demais! Amei o conteúdo!", "likes": 432, "replies_count": 8, "author": "rafael_mendes", "date": "5 dias atrás"},
    {"text": "Que vídeo lindo! Conteúdo de qualidade!", "likes": 398, "replies_count": 7, "author": "camila_ferreira", "date": "2 dias atrás"},
    {"text": "Excelente! Sempre me inspira muito!", "likes": 365, "replies_count": 6, "author": "lucas_almeida", "date": "1 dia atrás"},

    # Comentários neutros
    {"text": "Vídeo interessante, vou assistir até o fim", "likes": 234, "replies_count": 5, "author": "bruno_silva", "date": "3 dias atrás"},
    {"text": "Legal, mas queria mais detalhes sobre isso", "likes": 198, "replies_count": 4, "author": "isabela_costa", "date": "2 dias atrás"},
    {"text": "Bom conteúdo, continue assim!", "likes": 176, "replies_count": 3, "author": "thiago_lima", "date": "4 dias atrás"},
    {"text": "Interessante! Nunca tinha pensado nisso antes", "likes": 154, "replies_count": 2, "author": "larissa_santos", "date": "1 dia atrás"},
    {"text": "Que bom que você compartilhou isso!", "likes": 132, "replies_count": 2, "author": "gabriel_oliveira", "date": "5 dias atrás"},
    {"text": "Vídeo bacana! Valeu por compartilhar", "likes": 118, "replies_count": 1, "author": "amanda_rocha", "date": "2 dias atrás"},
    {"text": "Curioso! Vou ver mais vídeos seus", "likes": 95, "replies_count": 1, "author": "felipe_mendes", "date": "3 dias atrás"},
    {"text": "Legal o vídeo, mas poderia ser mais longo", "likes": 87, "replies_count": 0, "author": "patricia_ferreira", "date": "4 dias atrás"},

    # Comentários negativos
    {"text": "Não gostei muito do conteúdo desta vez", "likes": 156, "replies_count": 23, "author": "roberto_silva", "date": "2 dias atrás"},
    {"text": "Que decepcionante... esperava algo melhor", "likes": 134, "replies_count": 18, "author": "vanessa_costa", "date": "1 dia atrás"},
    {"text": "Ruim! Não recomendo assistir isso", "likes": 98, "replies_count": 12, "author": "eduardo_lima", "date": "3 dias atrás"},
    {"text": "Péssimo conteúdo, muito decepcionante", "likes": 76, "replies_count": 8, "author": "renata_santos", "date": "4 dias atrás"},
    {"text": "Horrível! Não entendi o que você quis dizer", "likes": 54, "replies_count": 5, "author": "marcos_oliveira", "date": "2 dias atrás"},
    {"text": "Que vergonha alheia... conteúdo horrível", "likes": 43, "replies_count": 3, "author": "leticia_rocha", "date": "5 dias atrás"},

    # Mais comentários variados
    {"text": "Muito bom! Conteúdo de qualidade como sempre!", "likes": 287, "replies_count": 9, "author": "diego_mendes", "date": "1 dia atrás"},
    {"text": "Que vídeo incrível! Amei a energia!", "likes": 245, "replies_count": 7, "author": "priscila_ferreira", "date": "3 dias atrás"},
    {"text": "Top! Sempre me divirto com seus vídeos", "likes": 198, "replies_count": 6, "author": "anderson_silva", "date": "2 dias atrás"},
    {"text": "Maravilhoso! Você é muito criativa!", "likes": 176, "replies_count": 5, "author": "beatriz_costa", "date": "4 dias atrás"},
    {"text": "Legal demais! Conteúdo sensacional!", "likes": 154, "replies_count": 4, "author": "vinicius_lima", "date": "1 dia atrás"},
    {"text": "Que vídeo lindo! Amei cada detalhe!", "likes": 132, "replies_count": 3, "author": "sabrina_santos", "date": "5 dias atrás"},
    {"text": "Excelente conteúdo! Sempre me inspira!", "likes": 118, "replies_count": 2, "author": "leonardo_oliveira", "date": "2 dias atrás"},
    {"text": "Fantástico! Você é a melhor criadora!", "likes": 95, "replies_count": 2, "author": "carolina_rocha", "date": "3 dias atrás"},
    {"text": "Incrível demais! Conteúdo de primeira!", "likes": 87, "replies_count": 1, "author": "matheus_mendes", "date": "4 dias atrás"},
    {"text": "Que vídeo bacana! Continue assim!", "likes": 65, "replies_count": 0, "author": "juliana_ferreira", "date": "1 dia atrás"},
]

MOCK_VIDEO_INFO = {
    "likes": "245.3K",
    "comment_count": "8.7K",
    "shares": "12.4K",
    "description": "Vídeo incrível sobre culinária! 🍳✨ #receita #cozinha #delícia"
}
