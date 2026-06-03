"""轻量级 BM25 检索器（零外部依赖，支持中英双语）。

- 英文：小写化后按非字母数字切词，去停用词，做简单复数还原（去尾随 s）。
- 中文：按字符切分并生成二元组（bigram），无需分词库即可有基本召回。

除 BM25 排序分外，还额外计算「内容词覆盖率」(coverage)：
查询中的实义词有多大比例命中了该文档。
这是判断「知识库是否真的有相关信息」的关键信号——
单纯的 BM25 归一化分对最相关文档恒为 1.0，无法用于阈值判断。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .knowledge_base import KBDoc, KnowledgeBase

_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")

_STOPWORDS = {
    "the", "a", "an", "of", "to", "for", "and", "or", "is", "are", "do", "does",
    "you", "your", "i", "we", "can", "could", "would", "will", "my", "me", "in",
    "on", "with", "what", "how", "much", "many", "it", "this", "that", "be", "have",
    "need", "want", "please", "next", "based", "make", "made", "get",
    "的", "了", "吗", "我", "你", "们", "是", "有", "请",
}


# 中文→英文术语表：知识库为英文，借此把中文查询桥接到英文知识。
_CN_EN_GLOSSARY = {
    "不锈钢": "stainless steel", "碳钢": "carbon steel", "铝": "aluminum",
    "支架": "bracket", "冲压": "stamping", "焊接": "welding welded",
    "框架": "frame", "材料": "material", "样品": "sample", "图纸": "drawing",
    "模型": "model", "公差": "tolerance", "表面处理": "surface treatment",
    "交期": "lead time", "起订量": "moq", "最小起订量": "moq",
    "定制": "custom oem", "报价": "quotation", "数量": "quantity",
    "玩具": "toy", "塑料": "plastic", "零件": "part",
}


def expand_query(text: str) -> str:
    """把查询中的中文术语追加其英文译名，桥接跨语言检索。"""
    extra = [en for cn, en in _CN_EN_GLOSSARY.items() if cn in text]
    return text + " " + " ".join(extra) if extra else text


def _stem(token: str) -> str:
    # 极简复数还原，让 bracket/brackets、part/parts 等可匹配
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = [_stem(t) for t in _WORD_RE.findall(text)]
    cjk = _CJK_RE.findall(text)
    tokens.extend(cjk)
    for a, b in zip(cjk, cjk[1:]):
        tokens.append(a + b)
    return tokens


def content_terms(text: str) -> set[str]:
    """实义词集合：去停用词、去单字噪音。

    仅统计 ASCII 实义词用于覆盖率判定——知识库为英文，中文 token 永远无法命中，
    会错误拉低覆盖率；中文语义已由 expand_query() 映射为英文术语后纳入统计。
    """
    out = set()
    for t in tokenize(expand_query(text)):
        if _CJK_RE.match(t):  # 跳过中文单字 / 二元组
            continue
        if t in _STOPWORDS or t.isdigit():
            continue
        out.add(t)
    return out


@dataclass
class RetrievalHit:
    doc: KBDoc
    score: float      # 归一化 BM25 排序分 0~1
    coverage: float   # 实义词覆盖率 0~1


class BM25Retriever:
    def __init__(self, kb: KnowledgeBase, k1: float = 1.5, b: float = 0.75):
        self.kb = kb
        self.k1 = k1
        self.b = b
        self._tokenized: list[list[str]] = [tokenize(d.text) for d in kb.docs]
        self._doc_terms: list[set[str]] = [set(t) for t in self._tokenized]
        self._doc_len = [len(t) for t in self._tokenized]
        self._avgdl = (sum(self._doc_len) / len(self._doc_len)) if self._doc_len else 0.0
        self._df: Counter[str] = Counter()
        for terms in self._doc_terms:
            for term in terms:
                self._df[term] += 1
        self._n = len(kb.docs)

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 4) -> list[RetrievalHit]:
        query = expand_query(query)  # 中文查询桥接到英文知识库
        q_terms = tokenize(query)
        if not q_terms:
            return []
        q_content = content_terms(query)

        raw_scores: list[float] = []
        for i, toks in enumerate(self._tokenized):
            tf = Counter(toks)
            dl = self._doc_len[i] or 1
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                idf = self._idf(term)
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                score += idf * (freq * (self.k1 + 1)) / denom
            raw_scores.append(score)

        max_score = max(raw_scores) if raw_scores else 0.0
        hits: list[RetrievalHit] = []
        for doc, raw, terms in zip(self.kb.docs, raw_scores, self._doc_terms):
            if raw <= 0:
                continue
            norm = raw / max_score if max_score > 0 else 0.0
            if q_content:
                coverage = len(q_content & terms) / len(q_content)
            else:
                coverage = 0.0
            hits.append(RetrievalHit(doc=doc, score=round(norm, 4),
                                     coverage=round(coverage, 4)))

        # 先按覆盖率、再按 BM25 排序，让真正相关的排前面
        hits.sort(key=lambda h: (h.coverage, h.score), reverse=True)
        return hits[:top_k]
