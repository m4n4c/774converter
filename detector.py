"""個人情報の検出モジュール。

正規表現(電話番号・メール・郵便番号・住所)と、
GiNZA がインストールされていれば固有表現抽出(人名・組織名)を併用する。
GiNZA が無い環境では正規表現のみで動作する。
"""

import re

# 優先度順(重なった場合は先のものを採用)
REGEX_PATTERNS = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("phone", re.compile(r"(?<![\d-])0\d{1,4}[-‐−ー()()]?\d{1,4}[-‐−ー()()]?\d{3,4}(?![\d-])")),
    ("postal", re.compile(r"〒\s*\d{3}[-‐−ー]?\d{4}|(?<![\d-])\d{3}[-‐−ー]\d{4}(?![\d-])")),
    (
        "address",
        re.compile(
            r"(?:北海道|東京都|京都府|大阪府|[一-龥]{2,3}県)"
            r"[一-龥ぁ-んァ-ヶーa-zA-Z0-9０-９]{1,30}?(?:市|区|郡|町|村)"
            r"[^\s、。,「」()()]{0,40}"
        ),
    ),
]

# 人名の直後に続く敬称
_HONORIFIC = re.compile(r"(?:さん|さま|様|氏|くん|君|ちゃん|殿|先生)")

# GiNZA の固有表現ラベル → このアプリでの種別
NER_LABEL_MAP = {
    "Person": "person",
    "Company": "org",
    "Corporation_Other": "org",
    "International_Organization": "org",
    "Show_Organization": "org",
    "Government": "org",
    "Political_Party": "org",
    "School": "org",
    "GPE_Other": None,  # 一般的な地名は住所正規表現に任せる
}

_nlp = None
_ginza_checked = False


def _get_nlp():
    """GiNZA モデルを遅延ロードする。無ければ None。"""
    global _nlp, _ginza_checked
    if not _ginza_checked:
        _ginza_checked = True
        try:
            import spacy

            # split_mode を明示しないと confection 1.3 系の検証で読み込みに失敗する
            _nlp = spacy.load(
                "ja_ginza",
                config={"components": {"compound_splitter": {"split_mode": "C"}}},
            )
        except Exception:
            _nlp = None
    return _nlp


def ginza_available() -> bool:
    return _get_nlp() is not None


def detect(text: str) -> list[dict]:
    """テキストから個人情報候補を検出する。

    Returns: [{"surface": str, "type": str, "count": int}] を出現順で返す。
    """
    spans = []  # (start, end, surface, type)

    for type_name, pattern in REGEX_PATTERNS:
        for m in pattern.finditer(text):
            spans.append((m.start(), m.end(), m.group(), type_name))

    nlp = _get_nlp()
    if nlp is not None:
        doc = nlp(text)
        for ent in doc.ents:
            mapped = NER_LABEL_MAP.get(ent.label_)
            if mapped:
                start, end = ent.start_char, ent.end_char
                if mapped == "person":
                    # 直後の敬称まで含める(「佐藤花子さん」→「Bさんさん」を防ぐ)
                    m = _HONORIFIC.match(text, end)
                    if m:
                        end = m.end()
                spans.append((start, end, text[start:end], mapped))

    # 重なりの解決: 開始位置順、同位置なら長い方を優先。先に採用した範囲と重なるものは捨てる
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    accepted = []
    last_end = -1
    for start, end, surface, type_name in spans:
        if start >= last_end:
            accepted.append((start, surface, type_name))
            last_end = end

    # 同一文字列はまとめて件数を数える(初出順を保つ)
    items: dict[tuple[str, str], dict] = {}
    for start, surface, type_name in accepted:
        key = (surface, type_name)
        if key in items:
            items[key]["count"] += 1
        else:
            items[key] = {"surface": surface, "type": type_name, "count": 1}
    return list(items.values())
