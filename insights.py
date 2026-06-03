"""
insights.py - Insights de marketing para avaliacao de criadores como midia.

Projetado para o CMO / media buyer avaliar um video/criador do TikTok como
espaco publicitario. Funcoes puras (sem Flask, sem rede), consumidas por
analyzer.run_analysis() / run_aggregated_analysis().

Conteudo:
  - engagement_rate(video_info)         -> taxa de engajamento + tier
  - purchase_intent(comments)           -> % de sinais de compra + exemplos
  - language_breakdown(comments)        -> distribuicao de idiomas (PT/EN/ES/outros)
  - topic_clusters(comments)            -> 6 clusters de tema por keywords
  - brand_safety_score(comments, summary) -> score 0-100 de seguranca de marca
  - post_performance_score(...)         -> score de desempenho do post 0-100

Dependencias: apenas stdlib (re, unicodedata, math, collections, typing).
langdetect e OPCIONAL: se instalada, melhora a deteccao de idioma; ausente,
cai numa heuristica de stopwords/caracteres.
"""
import re
import math
import unicodedata
from collections import Counter
from typing import List, Dict, Any

# --- langdetect opcional (melhora language_breakdown) ---
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0  # determinismo
    _HAS_LANGDETECT = True
except Exception:  # ImportError ou qualquer falha de import
    _HAS_LANGDETECT = False


# ============================================================
# CONSTANTES
# ============================================================

# --- Intencao de compra (sempre SEM acento e em minusculas; o texto e
#     normalizado/sem-acento antes do match) ---
PURCHASE_KEYWORDS_PT = [
    'onde compra', 'onde comprar', 'onde encontro', 'onde acho', 'onde vende',
    'quanto custa', 'quanto e', 'quanto ta', 'qual o preco', 'qual valor',
    'qual o valor', 'preco', 'valor', 'quero comprar', 'quero um', 'quero uma',
    'como compro', 'como comprar', 'tem link', 'manda o link', 'cade o link',
    'link na bio', 'link da', 'cupom', 'desconto', 'frete', 'parcela',
    'a venda', 'esta a venda', 'comprar',
]
PURCHASE_KEYWORDS_EN = [
    'where to buy', 'where can i buy', 'where do i get', 'how much', 'how much is',
    'price', 'cost', 'link please', 'drop the link', 'whats the link',
    'what is the link', 'link in bio', 'coupon', 'discount', 'promo code',
    'shipping', 'i want to buy', 'i need this', 'add to cart', 'buy this',
    'is it for sale', 'for sale', 'in stock', 'available',
]
PURCHASE_KEYWORDS_ES = [
    'donde compro', 'donde comprar', 'donde lo consigo', 'donde se vende',
    'cuanto cuesta', 'cuanto vale', 'que precio', 'el precio', 'precio',
    'quiero comprar', 'como compro', 'tienes el link', 'pasame el link',
    'el enlace', 'cupon', 'descuento', 'envio', 'a la venta', 'esta a la venta',
    'comprar',
]
# Lista unica (dedup preservando ordem PT > EN > ES)
PURCHASE_KEYWORDS = list(dict.fromkeys(
    PURCHASE_KEYWORDS_PT + PURCHASE_KEYWORDS_EN + PURCHASE_KEYWORDS_ES
))

# --- Faixas de tier de engajamento (pontos percentuais) ---
ENGAGEMENT_LOW_MAX = 1.0    # < 1%  -> baixo
ENGAGEMENT_GOOD_MAX = 3.0   # 1-3%  -> bom ; > 3% -> excelente

ENG_TIER_LABELS = {
    'baixo': 'Baixo',
    'bom': 'Bom',
    'excelente': 'Excelente',
    'indisponivel': 'Dados insuficientes',
}

# --- Stopwords EXCLUSIVAS por idioma (discriminam PT vs ES vs EN) ---
PT_STOPWORDS = {
    "nao", "não", "voce", "você", "muito", "muita", "tambem", "também",
    "como", "mais", "isso", "esse", "essa", "está", "esta", "estao", "estão",
    "sao", "são", "tem", "ter", "foi", "ser", "seu", "sua", "com", "uma",
    "por", "para", "pra", "pro", "dos", "das", "ele", "ela", "eles", "elas",
    "obrigado", "obrigada", "demais", "melhor", "sempre", "porque", "entao",
    "então", "agora", "aqui", "vai", "vou", "fazer", "gente", "coisa",
    "depois", "ainda", "tudo", "nada", "bem", "ja", "já",
}
EN_STOPWORDS = {
    "the", "and", "this", "that", "with", "you", "your", "for", "are",
    "was", "were", "have", "has", "his", "her", "they", "them", "but",
    "not", "what", "when", "where", "which", "who", "how", "all", "would",
    "there", "their", "about", "love", "great", "really", "amazing",
    "video", "best", "thanks", "thank", "please", "from", "just", "like",
    "good", "make", "made", "want", "need", "more", "much",
}
ES_STOPWORDS = {
    "pero", "muy", "tambien", "también", "como", "esto", "esta", "este",
    "estan", "están", "porque", "tiene", "tienen", "hacer", "siempre",
    "mejor", "gracias", "ahora", "aqui", "aquí", "todo", "nada", "ellos",
    "ellas", "para", "los", "las", "una", "con", "sus", "que", "del",
    "eres", "estoy", "estas", "tan", "asi", "así", "donde", "dónde",
    "cuando", "cuándo", "video", "encanta", "genial", "bonito", "hermoso",
}

# --- Keywords por cluster de topico (multi-label) ---
TOPIC_KEYWORDS = {
    "Música/Som": [
        "musica", "música", "song", "music", "som", "audio", "áudio",
        "beat", "trilha", "playlist", "remix", "cancao", "canção",
        "letra", "ritmo", "dança", "danca", "dance", "cantando",
        "qual a musica", "que musica", "nome da musica", "what song",
        "🎵", "🎶", "🎧", "🎤",
    ],
    "Produto/Marca": [
        "produto", "product", "marca", "brand", "comprar", "compra",
        "comprei", "buy", "bought", "preco", "preço", "price", "valor",
        "loja", "store", "shop", "link", "onde comprar", "where to buy",
        "vale a pena", "recomendo", "review", "resenha", "qualidade",
        "patrocinio", "patrocínio", "publi", "publicidade", "anuncio",
        "anúncio", "cupom", "desconto", "frete", "encomendar",
    ],
    "Humor": [
        "kkk", "kkkk", "rsrs", "haha", "hahaha", "lmao", "lol", "rofl",
        "piada", "engracado", "engraçado", "comedia", "comédia", "meme",
        "morri", "chorando de rir", "morrendo de rir", "que comedia",
        "funny", "hilarious", "joke", "😂", "🤣", "😆", "😹",
    ],
    "Emoção/Inspiração": [
        "amei", "amo", "love", "lindo", "linda", "lindo demais",
        "maravilhoso", "maravilhosa", "incrivel", "incrível", "inspirador",
        "inspiradora", "inspiracao", "inspiração", "emocionante", "emocionei",
        "chorei", "coracao", "coração", "deus", "abençoado", "abencoado",
        "perfeito", "perfeita", "sensacional", "espetacular", "conteudo",
        "conteúdo", "talento", "talentoso", "talentosa", "❤️", "😍", "🥰",
        "🔥", "👏", "😭",
    ],
    "Pergunta/CTA": [
        "como faz", "como fazer", "como voce", "como você", "qual",
        "quando", "onde", "porque", "por que", "quem", "alguem sabe",
        "alguém sabe", "me responde", "responde", "duvida", "dúvida",
        "pergunta", "how to", "how do", "what is", "where", "when",
        "why", "who", "can you", "could you", "?", "segue", "siga",
        "comenta", "compartilha", "marca alguem", "marca alguém",
        "manda pra", "link na bio", "swipe", "clica",
    ],
    "Spam/Promo": [
        "ganhe dinheiro", "renda extra", "trabalhe em casa", "clique aqui",
        "click here", "free money", "ganhar dinheiro", "investimento",
        "invista", "bitcoin", "cripto", "crypto", "telegram", "whatsapp",
        "chama no whats", "chama no zap", "segue de volta", "segue que sigo",
        "follow back", "f4f", "promo", "promocao", "promoção", "sorteio",
        "giveaway", "sigam meu", "visita meu perfil", "ver meu perfil",
        "link na descricao", "link na descrição", "💰", "🤑", "🛒",
    ],
}

# --- Hate / toxicidade (match por PALAVRA INTEIRA, PT + EN) ---
HATE_KEYWORDS = {
    # PT: ofensas / odio / violencia
    'lixo', 'merda', 'bosta', 'porcaria', 'idiota', 'imbecil', 'burro', 'burra',
    'otario', 'otaria', 'estupido', 'estupida', 'retardado', 'retardada',
    'nojento', 'nojenta', 'nojo', 'odeio', 'odiar', 'morra', 'morre',
    'vagabundo', 'vagabunda', 'vadia', 'puta', 'putaria', 'corno', 'fdp',
    'arrombado', 'arrombada', 'desgraca', 'desgracado', 'cuzao', 'babaca',
    'escroto', 'escrota', 'verme', 'parasita', 'demente', 'aberracao',
    'racista', 'racismo', 'viado', 'bicha', 'sapatao', 'traveco',
    'horroroso', 'horrorosa', 'patetico', 'patetica', 'fracassado',
    'fracassada', 'ridiculo', 'ridicula',
    # EN: insults / hate / violence
    'trash', 'garbage', 'idiot', 'idiots', 'stupid', 'dumb', 'moron', 'loser',
    'losers', 'ugly', 'disgusting', 'gross', 'hate', 'kill', 'die', 'retard',
    'retarded', 'scum', 'pathetic', 'worthless', 'racist', 'racism', 'nazi',
    'bitch', 'slut', 'whore', 'asshole', 'bastard', 'cunt', 'faggot', 'fag',
    'shit', 'crap', 'fraud', 'scam', 'fake', 'freak',
}

# link -> sinal de spam
SPAM_LINK_RE = re.compile(
    r'(https?://|www\.|\b[\w-]+\.(?:com|net|org|io|ru|br|co|me|link|shop|store|xyz)\b'
    r'|t\.me/|wa\.me/|bit\.ly|tinyurl)',
    re.IGNORECASE,
)

# remove emojis + simbolos + espacos; se sobrar vazio => 'so emoji'
EMOJI_ONLY_RE = re.compile(
    '['
    '\U0001F300-\U0001FAFF'   # pictographs / emoji estendido
    '\U00002600-\U000027BF'   # misc symbols + dingbats
    '\U0001F1E0-\U0001F1FF'   # bandeiras
    '\U00002000-\U0000206F'   # pontuacao geral
    '\U0000FE00-\U0000FE0F'   # variation selectors
    '\U00002190-\U000021FF'   # setas
    '‍♀♂❤'
    r'\s'
    ']+', flags=re.UNICODE,
)

# tokeniza incluindo acentos (Latin-1 supplement)
WORD_RE = re.compile(r'[\wÀ-ÿ]+', re.UNICODE)

# rotulos PT-BR para os componentes do APS
_PT_LABELS = {
    'engagement': 'engajamento', 'alcance': 'alcance',
    'brand_safety': 'seguranca de marca',
    'purchase_intent': 'intencao de compra', 'sentiment': 'sentimento',
}


# ============================================================
# HELPERS GERAIS
# ============================================================
def _to_int(value: Any) -> int:
    """Coercao defensiva: None / '' / ausente -> 0."""
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default


def _tier_from_score(score: float) -> str:
    """score > 80 -> verde ; 50-80 -> amarelo ; < 50 -> vermelho."""
    if score > 80:
        return 'verde'
    if score >= 50:
        return 'amarelo'
    return 'vermelho'


# --- Normalizacao para intencao de compra (remove acentos) ---
def _normalize(text: str) -> str:
    """Minusculas, sem acento, espacos colapsados (match PT/EN/ES robusto)."""
    if not text:
        return ''
    text = text.lower()
    nfkd = unicodedata.normalize('NFD', text)
    text = ''.join(ch for ch in nfkd if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', text).strip()


# --- Normalizacao para idioma/topicos (MANTEM acentos: sao sinal de idioma) ---
def _normalize_text(text: str) -> str:
    if not text:
        return ''
    t = text.lower()
    t = re.sub(r'http\S+|www\.\S+', ' ', t)
    t = re.sub(r'@\w+', ' ', t)
    t = t.replace('#', ' ')
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r'[a-zA-Zà-ÿÀ-ÿЀ-ӿ]+', text)


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r'[Ѐ-ӿ]', text))


_WORD_PATTERN_CACHE: Dict[str, "re.Pattern"] = {}


def _word_pattern(kw: str) -> "re.Pattern":
    p = _WORD_PATTERN_CACHE.get(kw)
    if p is None:
        p = re.compile(r'(?<!\w)' + re.escape(kw) + r'(?!\w)')
        _WORD_PATTERN_CACHE[kw] = p
    return p


def _is_plain_word(kw: str) -> bool:
    """So letras (com acento) e sem espaco -> tratavel como palavra."""
    return re.fullmatch(r'[a-zà-ÿ]+', kw) is not None


def _keyword_in(keyword: str, norm_text: str, raw_text: str) -> bool:
    """Matching de keyword de topico: palavra inteira / n-grama / emoji."""
    if ' ' in keyword:
        # n-grama textual: substring no texto normalizado (se for so letras),
        # senao no texto cru
        if all(_is_plain_word(p) for p in keyword.split() if p):
            return keyword in norm_text
        return keyword in raw_text
    if _is_plain_word(keyword):
        return _word_pattern(keyword).search(norm_text) is not None
    # emoji / pontuacao (ex '?') -> testa no texto cru
    return keyword in raw_text.lower()


# ============================================================
# 1) ENGAGEMENT RATE
# ============================================================
def engagement_rate(video_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Taxa de engajamento do video para avaliacao publicitaria.

    Formula: (likes + comments + shares + favorites) / plays * 100
    - 'comments' usa o total REAL do TikTok (video_info['comments']),
      nao os comentarios scrapeados (summary.total_comments).
    - Trata plays == 0 retornando tier 'indisponivel' (sem divisao por zero).

    Tiers: < 1% baixo | 1-3% bom | > 3% excelente.
    """
    likes = _to_int(video_info.get('likes'))
    comments = _to_int(video_info.get('comments'))
    shares = _to_int(video_info.get('shares'))
    favorites = _to_int(video_info.get('favorites'))
    plays = _to_int(video_info.get('plays'))

    engagements = likes + comments + shares + favorites

    if plays <= 0:
        return {
            'rate_pct': 0.0,
            'tier': 'indisponivel',
            'tier_label': ENG_TIER_LABELS['indisponivel'],
            'engagements': engagements,
            'plays': 0,
            'components': {
                'likes_pct': 0.0, 'comments_pct': 0.0,
                'shares_pct': 0.0, 'favorites_pct': 0.0,
            },
        }

    rate = engagements / plays * 100

    if rate < ENGAGEMENT_LOW_MAX:
        tier = 'baixo'
    elif rate <= ENGAGEMENT_GOOD_MAX:
        tier = 'bom'
    else:
        tier = 'excelente'

    return {
        'rate_pct': round(rate, 2),
        'tier': tier,
        'tier_label': ENG_TIER_LABELS[tier],
        'engagements': engagements,
        'plays': plays,
        'components': {
            'likes_pct': round(likes / plays * 100, 2),
            'comments_pct': round(comments / plays * 100, 2),
            'shares_pct': round(shares / plays * 100, 2),
            'favorites_pct': round(favorites / plays * 100, 2),
        },
    }


# ============================================================
# 2) PURCHASE INTENT
# ============================================================
def purchase_intent(comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detecta sinais de intencao de compra nos comentarios (PT/EN/ES).

    Match por substring em texto normalizado (lower + sem acento).
    Retorna intent_pct, intent_count, total_analyzed e ate 10 exemplos
    (ordenados por likes desc) com a keyword que disparou o match.
    """
    matched = []
    for c in comments:
        norm = _normalize(c.get('text', ''))
        if not norm:
            continue
        hit = next((kw for kw in PURCHASE_KEYWORDS if kw in norm), None)
        if hit:
            matched.append({
                'text': c.get('text', ''),
                'author': c.get('author', ''),
                'likes': _to_int(c.get('likes')),
                'matched_keyword': hit,
            })

    n = len(comments) or 1
    matched.sort(key=lambda x: x['likes'], reverse=True)

    return {
        'intent_pct': round(len(matched) / n * 100, 1),
        'intent_count': len(matched),
        'total_analyzed': len(comments),
        'examples': matched[:10],
    }


# ============================================================
# 3) LANGUAGE BREAKDOWN
# ============================================================
def language_breakdown(comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Distribuicao de idiomas dos comentarios (PT/EN/ES/outros).

    Usa langdetect se disponivel; senao, heuristica de stopwords + caracteres
    discriminantes. Comentarios em cirilico ou sem sinal caem em 'other'.
    """
    counts = {"pt": 0, "en": 0, "es": 0, "other": 0}

    for c in comments:
        raw = (c or {}).get("text", "") or ""
        txt = _normalize_text(raw)

        if not txt or len(txt) < 2:
            counts["other"] += 1
            continue

        # PASSO 1: cirilico (RU/UA) -> other
        if _has_cyrillic(raw):
            counts["other"] += 1
            continue

        # PASSO 2: langdetect opcional
        if _HAS_LANGDETECT:
            try:
                code = detect(txt)
                if code == "pt":
                    counts["pt"] += 1
                    continue
                if code == "en":
                    counts["en"] += 1
                    continue
                if code == "es":
                    counts["es"] += 1
                    continue
                counts["other"] += 1
                continue
            except Exception:
                pass  # cai na heuristica

        # PASSO 3: heuristica de stopwords + caracteres
        tokens = set(_tokenize(txt))
        pt_hits = len(tokens & PT_STOPWORDS)
        en_hits = len(tokens & EN_STOPWORDS)
        es_hits = len(tokens & ES_STOPWORDS)

        if re.search(r"[ãõâêôç]", txt):
            pt_hits += 2
        if re.search(r"[ñ]", txt) or re.search(r"[¿¡]", raw):
            es_hits += 2

        scores = {"pt": pt_hits, "en": en_hits, "es": es_hits}
        best = max(scores, key=lambda k: scores[k])

        if scores[best] == 0:
            counts["other"] += 1
        elif scores["es"] > scores["pt"] and scores["es"] >= scores["en"]:
            counts["es"] += 1
        elif scores["pt"] >= scores["en"] and scores["pt"] >= scores["es"]:
            counts["pt"] += 1
        else:
            counts[best] += 1

    total = len(comments) or 1
    distribution = {k: round(v / total * 100, 1) for k, v in counts.items()}
    order = ["pt", "en", "es", "other"]
    dominant = max(order, key=lambda k: (counts[k], -order.index(k)))

    return {
        "distribution": distribution,
        "dominant": dominant,
        "counts": counts,
        "total": len(comments),
    }


# ============================================================
# 4) TOPIC CLUSTERS
# ============================================================
def topic_clusters(comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classifica cada comentario em 0+ dos 6 clusters de tema (multi-label).
    A soma dos counts pode exceder o total (um comentario pode casar varios).
    """
    counts = Counter()

    for c in comments:
        raw = (c or {}).get("text", "") or ""
        norm = _normalize_text(raw)
        if not norm and not raw:
            continue
        for name, keywords in TOPIC_KEYWORDS.items():
            for kw in keywords:
                if _keyword_in(kw, norm, raw):
                    counts[name] += 1
                    break  # 1 hit ja classifica o comentario nesse cluster

    total = len(comments) or 1
    clusters = [
        {
            "name": name,
            "count": counts.get(name, 0),
            "pct": round(counts.get(name, 0) / total * 100, 1),
        }
        for name in TOPIC_KEYWORDS
    ]
    clusters.sort(key=lambda x: x["count"], reverse=True)

    return {"clusters": clusters, "total": len(comments)}


# ============================================================
# 5) BRAND SAFETY SCORE
# ============================================================
def _is_spam_comment(text: str) -> bool:
    """True se for link, muito curto (<3) ou so emoji/simbolos."""
    if not text:
        return True
    s = text.strip()
    if SPAM_LINK_RE.search(s):
        return True
    if len(s) < 3:
        return True
    if EMOJI_ONLY_RE.sub('', s).strip() == '':
        return True
    return False


def _count_toxic(comments: List[Dict]) -> int:
    """Conta comentarios com >=1 hate keyword (match por palavra inteira)."""
    count = 0
    for c in comments:
        text = (c.get('text') or '').lower()
        tokens = set(WORD_RE.findall(text))
        if HATE_KEYWORDS & tokens:
            count += 1
    return count


def brand_safety_score(comments: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Score 0-100 de seguranca de marca (maior = mais seguro).

    Penaliza: % negativos, % toxicidade (maior peso), % spam e baixa
    diversidade de autores (poucos autores repetindo = sinal de bot/spam).
    Usa n = comentarios ANALISADOS (summary.total_comments), exposto no
    breakdown como 'analyzed_comments'.
    """
    n = int(summary.get('total_comments') or len(comments) or 0)
    if n <= 0:
        return {'score': 0.0, 'tier': 'vermelho', 'breakdown': {
            'negative_pct': 0.0, 'toxicity_pct': 0.0, 'toxic_count': 0,
            'spam_pct': 0.0, 'spam_count': 0, 'author_diversity_pct': 0.0,
            'unique_authors': 0, 'analyzed_comments': 0,
            'penalties': {'negativos': 0.0, 'toxicidade': 0.0,
                          'spam': 0.0, 'baixa_diversidade': 0.0}}}

    neg_pct = float(summary.get('negative_pct', 0.0))

    toxic_count = _count_toxic(comments)
    toxic_pct = _safe_div(toxic_count, n) * 100.0

    spam_count = sum(1 for c in comments if _is_spam_comment(c.get('text', '')))
    spam_pct = _safe_div(spam_count, n) * 100.0

    unique_authors = len({(c.get('author') or '').strip().lower()
                          for c in comments if (c.get('author') or '').strip()})
    diversity_pct = _clamp(_safe_div(unique_authors, n) * 100.0)

    W_NEG, W_TOX, W_SPAM, W_DIV = 0.5, 2.0, 0.3, 0.15
    p_neg = W_NEG * neg_pct
    p_tox = W_TOX * toxic_pct
    p_spam = W_SPAM * spam_pct
    p_div = W_DIV * (100.0 - diversity_pct)

    score = round(_clamp(100.0 - p_neg - p_tox - p_spam - p_div), 1)
    return {
        'score': score,
        'tier': _tier_from_score(score),
        'breakdown': {
            'negative_pct': round(neg_pct, 1),
            'toxicity_pct': round(toxic_pct, 2),
            'toxic_count': toxic_count,
            'spam_pct': round(spam_pct, 1),
            'spam_count': spam_count,
            'author_diversity_pct': round(diversity_pct, 1),
            'unique_authors': unique_authors,
            'analyzed_comments': n,
            'penalties': {
                'negativos': round(p_neg, 1),
                'toxicidade': round(p_tox, 1),
                'spam': round(p_spam, 1),
                'baixa_diversidade': round(p_div, 1),
            },
        },
    }


# ============================================================
# 6) POST PERFORMANCE SCORE (composto) — o post JÁ é uma publi veiculada;
#    medimos o DESEMPENHO do post, não potencial de compra de mídia.
# ============================================================
def _fmt_plays(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'.replace('.', ',')
    if n >= 1_000:
        return f'{n/1_000:.1f}k'.replace('.', ',')
    return str(n)


def _build_justification(score, tier, components, contributions, video_info):
    """Texto PT-BR explicando o desempenho do post para o time de marketing."""
    head = {'verde': 'Post de alto desempenho.',
            'amarelo': 'Desempenho moderado, com pontos a melhorar.',
            'vermelho': 'Baixo desempenho — revisar criativo/abordagem.'}[tier]
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    fortes = [_PT_LABELS[k] for k, _ in ranked[:2]]
    fraco_key = ranked[-1][0]
    fraco = _PT_LABELS[fraco_key]
    plays = video_info.get('plays') if isinstance(video_info, dict) else None
    destaque_alcance = ''
    if 'alcance' in fortes and plays:
        destaque_alcance = f' ({_fmt_plays(plays)} de visualizacoes)'
    fortes_txt = ' e '.join(fortes)
    return (f'Desempenho do post: {int(round(score))}/100 ({tier}). {head} '
            f'Destaques: {fortes_txt}{destaque_alcance}. '
            f'Ponto de atencao: {fraco} ({components.get(fraco_key, 0):.0f}/100).')


def post_performance_score(engagement: Dict, brand_safety: Dict,
                           purchase_intent: Dict, summary: Dict,
                           video_info: Dict) -> Dict[str, Any]:
    """
    Score de DESEMPENHO do post (0-100). O post analisado já é uma publicidade
    veiculada — este score mede como ele performou, não potencial de mídia.

    Pesos (foco em performance de uma publi entregue):
      engajamento 0.30, sentimento/recepção 0.25, intenção de compra 0.20,
      alcance(plays) 0.15, brand_safety 0.10. Cada componente normalizado 0-100.
    """
    engagement = engagement or {}
    brand_safety = brand_safety or {}
    purchase_intent = purchase_intent or {}
    summary = summary or {}
    video_info = video_info or {}

    # ENGAGEMENT (0-100): 0% -> 0, 6%+ -> 100. Le rate_pct (contrato canonico).
    eng_rate = float(engagement.get('rate_pct',
                     engagement.get('rate',
                     engagement.get('engagement_rate', 0.0))) or 0.0)
    c_eng = _clamp(eng_rate / 6.0 * 100.0)

    # ALCANCE/plays (0-100): log10 de 1k..100M
    plays = float(video_info.get('plays', 0) or 0)
    if plays <= 1_000:
        c_reach = 0.0
    else:
        c_reach = _clamp((math.log10(plays) - 3.0) / (8.0 - 3.0) * 100.0)

    # BRAND SAFETY (ja 0-100)
    c_safety = _clamp(float(brand_safety.get('score', 0.0) or 0.0))

    # PURCHASE INTENT (0-100): 0% -> 0, 15%+ -> 100 (eficacia da publi)
    pi_pct = float(purchase_intent.get('intent_pct',
                   purchase_intent.get('pct',
                   purchase_intent.get('percentage', 0.0))) or 0.0)
    c_intent = _clamp(pi_pct / 15.0 * 100.0)

    # SENTIMENT/recepção (0-100): polaridade -1..1 -> 0..100
    avg_pol = float(summary.get('avg_polarity', 0.0) or 0.0)
    c_sent = _clamp((avg_pol + 1.0) / 2.0 * 100.0)

    weights = {'engagement': 0.30, 'sentiment': 0.25, 'purchase_intent': 0.20,
               'alcance': 0.15, 'brand_safety': 0.10}
    components = {'engagement': c_eng, 'alcance': c_reach,
                  'brand_safety': c_safety, 'purchase_intent': c_intent,
                  'sentiment': c_sent}
    contributions = {k: round(weights[k] * components[k], 1) for k in weights}

    score = round(_clamp(sum(weights[k] * components[k] for k in weights)), 1)
    tier = _tier_from_score(score)
    justification = _build_justification(score, tier, components,
                                         contributions, video_info)

    return {
        'score': score,
        'tier': tier,
        'justification': justification,
        'components': {k: round(v, 1) for k, v in components.items()},
        'weights': weights,
        'contributions': contributions,
    }
