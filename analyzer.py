"""
Análise de Sentimento e Word Cloud para comentários do TikTok
"""
import os
import re
from collections import Counter
from typing import List, Dict, Any

from textblob import TextBlob

import nltk
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from wordcloud import WordCloud
import matplotlib
matplotlib.use('Agg')  # Backend não-interativo
import matplotlib.pyplot as plt


class SentimentAnalyzer:
    """Analisador de sentimento com suporte a português e inglês."""

    POSITIVE_PT = {
        'bom', 'boa', 'ótimo', 'ótima', 'excelente', 'incrível', 'maravilhoso',
        'lindo', 'linda', 'bonito', 'bonita', 'amei', 'adorei', 'fantástico',
        'perfeito', 'genial', 'top', 'show', 'legal', 'gostei', 'sensacional',
        'espetacular', 'impressionante', 'adorável', 'encantador', 'magnífico',
        'sublime', 'divino', 'extraordinário', 'prodigioso', 'notável',
        'formidável', 'brilhante', 'radiante', 'esplêndido', 'glorioso',
        'triunfante', 'vitorioso', 'curti', 'top demais',
    }

    NEGATIVE_PT = {
        'ruim', 'péssimo', 'horrível', 'terrível', 'nojento', 'odiei',
        'desgostei', 'chato', 'chatice', 'aborrecido', 'triste', 'feio',
        'horrendo', 'repugnante', 'disgustoso', 'infeliz', 'decepcionante',
        'frustrante', 'irritante', 'desagradável', 'desconfortável',
        'desolador', 'desprezível', 'detestável', 'doloroso', 'fatal',
        'funesto', 'lúgubre', 'macabro', 'maldito', 'medonho',
        'monstruoso', 'odiando', 'hate', 'bad', 'ugly',
    }

    def __init__(self):
        self.stop_words = set(stopwords.words('portuguese')) | set(stopwords.words('english'))
        # Mantém palavras que podem ser relevantes para análise
        self.stop_words -= {'não', 'muito', 'mais', 'também', 'já', 'ainda', 'só', 'mas', 'nem'}

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analisa o sentimento de um texto. Retorna polarity, label e confidence."""
        if not text or not text.strip():
            return {'polarity': 0.0, 'label': 'neutral', 'confidence': 0.0}

        clean_text = self._clean_text(text)
        pt_score = self._analyze_portuguese(clean_text.lower())

        try:
            blob = TextBlob(clean_text)
            en_polarity = blob.sentiment.polarity
        except Exception:
            en_polarity = 0.0

        is_portuguese = self._detect_portuguese(text)
        if is_portuguese:
            polarity = pt_score * 0.7 + en_polarity * 0.3
        else:
            polarity = en_polarity * 0.7 + pt_score * 0.3

        if polarity > 0.15:
            label = 'positive'
        elif polarity < -0.15:
            label = 'negative'
        else:
            label = 'neutral'

        return {
            'polarity': round(polarity, 4),
            'label': label,
            'confidence': round(abs(polarity), 4),
        }

    def _clean_text(self, text: str) -> str:
        """Limpa o texto removendo emojis e caracteres especiais."""
        text = re.sub(r'http\S+|www\.\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#', '', text)
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub('', text)
        text = re.sub(r'[^a-zA-ZÀ-ÿ0-9\s]', ' ', text)
        return text.strip()

    def _detect_portuguese(self, text: str) -> bool:
        """Detecta se o texto está em português."""
        pt_indicators = ['o', 'a', 'de', 'que', 'e', 'em', 'um', 'para', 'com', 'não',
                        'uma', 'os', 'do', 'das', 'no', 'nos', 'mais', 'pelo', 'pela']
        text_lower = text.lower()
        count = sum(1 for word in pt_indicators if word in text_lower.split())
        return count >= 2

    def _analyze_portuguese(self, text: str) -> float:
        """Analisa sentimento baseado em palavras-chave em português."""
        words = text.lower().split()
        pos_count = sum(1 for w in words if w in self.POSITIVE_PT)
        neg_count = sum(1 for w in words if w in self.NEGATIVE_PT)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        score = (pos_count - neg_count) / total
        return score

    def analyze_all(self, comments: List[Dict]) -> Dict[str, Any]:
        """Analisa todos os comentários."""
        results = []
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        total_polarity = 0.0

        for comment in comments:
            sentiment = self.analyze_sentiment(comment.get('text', ''))
            result = {
                **comment,
                'sentiment': sentiment['label'],
                'polarity': sentiment['polarity'],
                'confidence': sentiment['confidence'],
            }
            results.append(result)
            sentiment_counts[sentiment['label']] += 1
            total_polarity += sentiment['polarity']

        avg_polarity = total_polarity / len(comments) if comments else 0.0

        return {
            'comments': results,
            'summary': {
                'total_comments': len(comments),
                'positive_count': sentiment_counts['positive'],
                'negative_count': sentiment_counts['negative'],
                'neutral_count': sentiment_counts['neutral'],
                'positive_pct': round(sentiment_counts['positive'] / max(len(comments), 1) * 100, 1),
                'negative_pct': round(sentiment_counts['negative'] / max(len(comments), 1) * 100, 1),
                'neutral_pct': round(sentiment_counts['neutral'] / max(len(comments), 1) * 100, 1),
                'avg_polarity': round(avg_polarity, 4),
            },
        }


class WordCloudGenerator:
    """Gerador de word cloud a partir dos comentários."""

    def __init__(self):
        self.stop_words = set(stopwords.words('portuguese')) | set(stopwords.words('english'))
        self.stop_words -= {'não', 'muito', 'mais', 'também', 'já', 'ainda', 'só', 'mas'}
        self.stop_words |= {w for w in self.stop_words if len(w) <= 2}

    def generate(self, comments: List[Dict], output_path: str = None):
        """Gera word cloud a partir dos comentários."""
        all_text = ' '.join(c.get('text', '') for c in comments if c.get('text'))

        if not all_text.strip():
            return None, {}

        clean_text = re.sub(r'http\S+|www\.\S+', '', all_text)
        clean_text = re.sub(r'@\w+', '', clean_text)
        clean_text = re.sub(r'#', '', clean_text)
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE,
        )
        clean_text = emoji_pattern.sub('', clean_text)

        try:
            tokens = word_tokenize(clean_text.lower())
        except Exception:
            tokens = clean_text.lower().split()

        filtered_tokens = [
            t for t in tokens
            if len(t) > 2 and t not in self.stop_words and t.isalpha()
        ]

        word_freq = Counter(filtered_tokens)
        top_words = dict(word_freq.most_common(100))

        if not top_words:
            return None, {}

        if output_path is None:
            output_path = 'static/wordcloud.png'

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        wordcloud = WordCloud(
            width=1200,
            height=600,
            background_color='#1a1a2e',
            colormap='viridis',
            max_words=200,
            min_font_size=8,
            max_font_size=120,
            contour_width=1,
            contour_color='steelblue',
            collocations=False,
        ).generate_from_frequencies(top_words)

        fig, ax = plt.subplots(figsize=(15, 8))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        ax.set_title('Word Cloud - Comentários TikTok', fontsize=20, color='white', pad=20)
        fig.patch.set_facecolor('#1a1a2e')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
        plt.close(fig)

        return output_path, top_words


def run_analysis(comments: List[Dict]) -> Dict[str, Any]:
    """Executa toda a análise nos comentários."""
    # Análise de sentimento
    analyzer = SentimentAnalyzer()
    sentiment_data = analyzer.analyze_all(comments)

    # Word cloud
    wc_generator = WordCloudGenerator()
    wc_path, top_words = wc_generator.generate(comments)

    # Ordena por likes e respostas
    sorted_by_likes = sorted(sentiment_data['comments'], key=lambda x: x.get('likes', 0), reverse=True)
    sorted_by_replies = sorted(sentiment_data['comments'], key=lambda x: x.get('replies_count', 0), reverse=True)

    # Palavras mais frequentes (top 50)
    all_text = ' '.join(c.get('text', '') for c in comments if c.get('text'))
    clean_all = re.sub(r'http\S+|www\.\S+|@\w+', '', all_text).lower()
    emoji_pattern = re.compile(
        "[" u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF" u"\U0001F1E0-\U0001F1FF" "]+", flags=re.UNICODE)
    clean_all = emoji_pattern.sub('', clean_all)

    stop_words_pt_en = set(stopwords.words('portuguese')) | set(stopwords.words('english'))
    try:
        tokens = word_tokenize(clean_all)
    except Exception:
        tokens = clean_all.split()

    filtered = [t for t in tokens if len(t) > 2 and t not in stop_words_pt_en and t.isalpha()]
    word_freq = Counter(filtered).most_common(50)

    return {
        'summary': sentiment_data['summary'],
        'top_comments_by_likes': [
            {'text': c.get('text', ''), 'author': c.get('author', ''),
             'likes': c.get('likes', 0), 'sentiment': c.get('sentiment', 'neutral'),
             'polarity': c.get('polarity', 0)}
            for c in sorted_by_likes[:20]
        ],
        'top_comments_by_replies': [
            {'text': c.get('text', ''), 'author': c.get('author', ''),
             'replies_count': c.get('replies_count', 0),
             'sentiment': c.get('sentiment', 'neutral')}
            for c in sorted_by_replies[:20]
        ],
        'top_words': [{'word': w, 'count': n} for w, n in word_freq],
        'wordcloud_path': wc_path,
        'sentiment_distribution': {
            'positive': sentiment_data['summary']['positive_pct'],
            'negative': sentiment_data['summary']['negative_pct'],
            'neutral': sentiment_data['summary']['neutral_pct'],
        },
    }
