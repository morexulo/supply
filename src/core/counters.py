from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_STATE: Dict[str, Any] = {"arp_id": "", "year_prefix": "26", "UX": 0, "UE": 0}

def _ensure_state(path: Path) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_STATE.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    for k, v in DEFAULT_STATE.items():
        data.setdefault(k, v)
    return data

def load_state(path: str | Path) -> Dict[str, Any]:
    return _ensure_state(Path(path))

def save_state(state: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def next_value(kind: str, path: str | Path) -> int:
    if kind not in ("UX", "UE"):
        raise ValueError("kind debe ser 'UX' o 'UE'")
    st = load_state(path)
    st[kind] = int(st.get(kind, 0)) + 1
    save_state(st, path)
    return st[kind]
