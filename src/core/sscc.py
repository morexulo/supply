from __future__ import annotations
from pathlib import Path
import yaml
from .counters import next_value

CFG_DEF = "config/config.da.yaml"

def load_cfg(cfg_path: str | Path = CFG_DEF) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def calc_check_digit(base17: str) -> int:
    digits = [int(c) for c in base17 if c.isdigit()]
    if len(digits) != 17:
        raise ValueError("base17 debe tener 17 dígitos")
    total = 0
    for i, d in enumerate(reversed(digits), start=1):
        w = 3 if i % 2 == 1 else 1
        total += d * w
    return (10 - (total % 10)) % 10

def _seq_block(year_prefix: str, seq: int) -> str:
    yp = "".join(ch for ch in str(year_prefix) if ch.isdigit())
    if len(yp) > 10:
        raise ValueError("year_prefix demasiado largo")
    width = 10 - len(yp)
    if seq < 0 or seq >= 10**width:
        raise ValueError("seq fuera de rango para el prefix dado")
    return f"{yp}{seq:0{width}d}"

def make_sscc(arp_id: str, seq: int, year_prefix: str) -> str:
    if not (arp_id and arp_id.isdigit() and len(arp_id) == 6):
        raise ValueError("arp_id debe ser 6 dígitos")
    block = _seq_block(year_prefix, seq)
    base17 = f"0{arp_id}{block}"
    cd = calc_check_digit(base17)
    return base17 + str(cd)

def next_ux(cfg_path: str | Path = CFG_DEF) -> str:
    cfg = load_cfg(cfg_path)
    st_path = cfg["sscc"]["state_path"]
    arp_id = cfg["arp_id"]
    ypref = cfg["sscc"]["year_prefix"]
    seq = next_value("UX", st_path)
    return make_sscc(arp_id, seq, ypref)

def next_ue(cfg_path: str | Path = CFG_DEF) -> str:
    cfg = load_cfg(cfg_path)
    st_path = cfg["sscc"]["state_path"]
    arp_id = cfg["arp_id"]
    ypref = cfg["sscc"]["year_prefix"]
    seq = next_value("UE", st_path)
    return make_sscc(arp_id, seq, ypref)

if __name__ == "__main__":
    print("UX:", next_ux())
    print("UE:", next_ue())
