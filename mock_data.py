"""
Dados mock para teste do dashboard sem necessidade de scraping real.
Use quando o TikTok bloquear o acesso ou para testes rapidos.
"""

MOCK_COMMENTS = [
    # Comentarios positivos
    {"text": "Que video incrivel! Amei demais!", "likes": 1520, "replies_count": 45, "author": "maria_silva", "date": "2 dias atras"},
    {"text": "Top demais! Conteudo excelente como sempre", "likes": 987, "replies_count": 32, "author": "joao_pereira", "date": "1 dia atras"},
    {"text": "Maravilhoso! Voce e muito talentosa!", "likes": 856, "replies_count": 28, "author": "ana_costa", "date": "3 dias atras"},
    {"text": "Perfeito! Adorei cada segundo deste video", "likes": 743, "replies_count": 19, "author": "carlos_lima", "date": "2 dias atras"},
    {"text": "Lindo demais! Que conteudo maravilhoso!", "likes": 654, "replies_count": 15, "author": "julia_santos", "date": "1 dia atras"},
    {"text": "Show de bola! Conteudo sensacional!", "likes": 521, "replies_count": 12, "author": "pedro_oliveira", "date": "4 dias atras"},
    {"text": "Fantastico! Voce e a melhor!", "likes": 498, "replies_count": 10, "author": "fernanda_rocha", "date": "3 dias atras"},
    {"text": "Incrivel demais! Amei o conteudo!", "likes": 432, "replies_count": 8, "author": "rafael_mendes", "date": "5 dias atras"},
    {"text": "Que video lindo! Conteudo de qualidade!", "likes": 398, "replies_count": 7, "author": "camila_ferreira", "date": "2 dias atras"},
    {"text": "Excelente! Sempre me inspira muito!", "likes": 365, "replies_count": 6, "author": "lucas_almeida", "date": "1 dia atras"},

    # Comentarios neutros
    {"text": "Video interessante, vou assistir ate o fim", "likes": 234, "replies_count": 5, "author": "bruno_silva", "date": "3 dias atras"},
    {"text": "Legal, mas queria mais detalhes sobre isso", "likes": 198, "replies_count": 4, "author": "isabela_costa", "date": "2 dias atras"},
    {"text": "Bom conteudo, continue assim!", "likes": 176, "replies_count": 3, "author": "thiago_lima", "date": "4 dias atras"},
    {"text": "Interessante! Nunca tinha pensado nisso antes", "likes": 154, "replies_count": 2, "author": "larissa_santos", "date": "1 dia atras"},
    {"text": "Que bom que voce compartilhou isso!", "likes": 132, "replies_count": 2, "author": "gabriel_oliveira", "date": "5 dias atras"},
    {"text": "Video bacana! Valeu por compartilhar", "likes": 118, "replies_count": 1, "author": "amanda_rocha", "date": "2 dias atras"},
    {"text": "Curioso! Vou ver mais videos seus", "likes": 95, "replies_count": 1, "author": "felipe_mendes", "date": "3 dias atras"},
    {"text": "Legal o video, mas poderia ser mais longo", "likes": 87, "replies_count": 0, "author": "patricia_ferreira", "date": "4 dias atras"},

    # Comentarios negativos
    {"text": "Nao gostei muito do conteudo desta vez", "likes": 156, "replies_count": 23, "author": "roberto_silva", "date": "2 dias atras"},
    {"text": "Que decepcionante... esperava algo melhor", "likes": 134, "replies_count": 18, "author": "vanessa_costa", "date": "1 dia atras"},
    {"text": "Ruim! Nao recomendo assistir isso", "likes": 98, "replies_count": 12, "author": "eduardo_lima", "date": "3 dias atras"},
    {"text": "Pessimo conteudo, muito decepcionante", "likes": 76, "replies_count": 8, "author": "renata_santos", "date": "4 dias atras"},
    {"text": "Horrible! Nao entendi o que voce quis dizer", "likes": 54, "replies_count": 5, "author": "marcos_oliveira", "date": "2 dias atras"},
    {"text": "Que vergonha alheia... conteudo horrivel", "likes": 43, "replies_count": 3, "author": "leticia_rocha", "date": "5 dias atras"},

    # Mais comentarios variados
    {"text": "Muito bom! Conteudo de qualidade como sempre!", "likes": 287, "replies_count": 9, "author": "diego_mendes", "date": "1 dia atras"},
    {"text": "Que video incrivel! Amei a energia!", "likes": 245, "replies_count": 7, "author": "priscila_ferreira", "date": "3 dias atras"},
    {"text": "Top! Sempre me divirto com seus videos", "likes": 198, "replies_count": 6, "author": "anderson_silva", "date": "2 dias atras"},
    {"text": "Maravilhoso! Voce e muito criativa!", "likes": 176, "replies_count": 5, "author": "beatriz_costa", "date": "4 dias atras"},
    {"text": "Legal demais! Conteudo sensacional!", "likes": 154, "replies_count": 4, "author": "vinicius_lima", "date": "1 dia atras"},
    {"text": "Que video lindo! Amei cada detalhe!", "likes": 132, "replies_count": 3, "author": "sabrina_santos", "date": "5 dias atras"},
    {"text": "Excelente conteudo! Sempre me inspira!", "likes": 118, "replies_count": 2, "author": "leonardo_oliveira", "date": "2 dias atras"},
    {"text": "Fantastico! Voce e a melhor criadora!", "likes": 95, "replies_count": 2, "author": "carolina_rocha", "date": "3 dias atras"},
    {"text": "Incrivel demais! Conteudo de primeira!", "likes": 87, "replies_count": 1, "author": "matheus_mendes", "date": "4 dias atras"},
    {"text": "Que video bacana! Continue assim!", "likes": 65, "replies_count": 0, "author": "juliana_ferreira", "date": "1 dia atras"},

    # Comentarios com sinais de intencao de compra (PT / EN / ES)
    {"text": "Quanto custa esse produto? Tem link na bio?", "likes": 312, "replies_count": 14, "author": "compradora_ana", "date": "1 dia atras"},
    {"text": "Onde comprar? Quero um desses agora!", "likes": 289, "replies_count": 11, "author": "lucas_consumidor", "date": "2 dias atras"},
    {"text": "Where to buy this? How much is it?", "likes": 201, "replies_count": 8, "author": "global_buyer", "date": "1 dia atras"},
    {"text": "Cuanto cuesta? Donde lo compro?", "likes": 167, "replies_count": 5, "author": "cliente_es", "date": "3 dias atras"},
    {"text": "Tem cupom de desconto? Qual o preco com frete?", "likes": 143, "replies_count": 4, "author": "economiza_ja", "date": "2 dias atras"},
]

MOCK_VIDEO_INFO = {
    "likes": 245300,
    "comments": 8700,
    "shares": 12400,
    "favorites": 3200,
    "plays": 1_245_000,
    "title": "Video incrivel sobre culinaria! #receita #cozinha",
    "author_name": "Chef Mock",
    "author_unique_id": "chef_mock",
}