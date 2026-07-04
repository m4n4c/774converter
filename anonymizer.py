"""置換(仮名化)と復元のロジック。

ラベルは人間が読みやすい形式:
  人名   → Aさん, Bさん, ... Zさん, AAさん, ...
  組織   → 会社A, 会社B, ...
  住所   → 住所1, 住所2, ...
  電話   → 電話番号1, ...
  メール → メール1, ...
  郵便   → 郵便番号1, ...
  その他 → その他1, ...
"""

import json
import string
from datetime import datetime
from pathlib import Path

MAPPINGS_DIR = Path(__file__).parent / "mappings"

TYPE_NAMES_JA = {
    "person": "人名",
    "org": "組織",
    "address": "住所",
    "phone": "電話番号",
    "email": "メール",
    "postal": "郵便番号",
    "other": "その他",
}


def _alpha_series(n: int) -> str:
    """0→A, 1→B, ... 25→Z, 26→AA のような英字連番。"""
    letters = string.ascii_uppercase
    result = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = letters[rem] + result
    return result


def _label_for(type_name: str, index: int) -> str:
    if type_name == "person":
        return f"{_alpha_series(index)}さん"
    if type_name == "org":
        return f"会社{_alpha_series(index)}"
    prefix = {
        "address": "住所",
        "phone": "電話番号",
        "email": "メール",
        "postal": "郵便番号",
    }.get(type_name, "その他")
    return f"{prefix}{index + 1}"


def build_mapping(text: str, items: list[dict]) -> list[dict]:
    """採用された検出項目にラベルを割り当てる。

    - 同じ文字列には同じラベル
    - 元テキストに既に含まれる文字列とラベルが衝突したら次の候補へ
    Returns: [{"label", "original", "type"}]
    """
    mapping = []
    used_labels = set()
    counters: dict[str, int] = {}
    seen: dict[str, str] = {}  # original -> label

    for item in items:
        original = item["surface"]
        type_name = item.get("type", "other")
        if original in seen:
            continue
        index = counters.get(type_name, 0)
        while True:
            label = _label_for(type_name, index)
            index += 1
            # 元テキストに同じ表現があると復元時に区別できないため避ける
            if label not in used_labels and label not in text:
                break
        counters[type_name] = index
        used_labels.add(label)
        seen[original] = label
        mapping.append({"label": label, "original": original, "type": type_name})
    return mapping


def anonymize(text: str, mapping: list[dict]) -> str:
    """長い文字列から順に置換し、部分一致の取り違えを防ぐ。"""
    for entry in sorted(mapping, key=lambda e: -len(e["original"])):
        text = text.replace(entry["original"], entry["label"])
    return text


def restore(text: str, mapping: list[dict]) -> str:
    """ラベルを元の文字列に戻す。「住所10」を「住所1」より先に処理する。"""
    for entry in sorted(mapping, key=lambda e: -len(e["label"])):
        text = text.replace(entry["label"], entry["original"])
    return text


def save_mapping(mapping: list[dict], title: str = "") -> str:
    MAPPINGS_DIR.mkdir(exist_ok=True)
    name = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "title": title,
        "items": mapping,
    }
    (MAPPINGS_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return name


def list_mappings() -> list[dict]:
    if not MAPPINGS_DIR.exists():
        return []
    result = []
    for path in sorted(MAPPINGS_DIR.glob("mapping_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append(
                {
                    "name": path.name,
                    "created": data.get("created", ""),
                    "title": data.get("title", ""),
                    "count": len(data.get("items", [])),
                }
            )
        except Exception:
            continue
    return result


def load_mapping(name: str) -> list[dict]:
    # パス操作を防ぐためファイル名のみ許可
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("invalid name")
    path = MAPPINGS_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("items", [])
