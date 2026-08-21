class QualityScorer:
    def score(self, title: str, text: str, headers: list[str], links_count: int) -> int:
        score = 0
        if title:
            score += 2
        if len(text) > 500:
            score += 3
        elif len(text) > 200:
            score += 2
        elif len(text) > 50:
            score += 1
        score += min(3, len(headers))
        score += min(2, links_count // 25)
        return min(10, score)