from __future__ import annotations
import os
import re
from pathlib import Path
import unicodedata
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime as _dt

try:
    import easyocr  # type: ignore
except Exception:  # easyocr is optional
    easyocr = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None  # type: ignore

try:
    from PIL import Image, ImageOps, ImageFilter  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageOps = None
    ImageFilter = None

# canonical TF mapping
_TF_MAP: Dict[str, str] = {
    # minutes
    "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m", "45": "45m",
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "45m": "45m",
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m", "M45": "45m",
    # hours
    "60": "1h", "120": "2h", "240": "4h", "360": "6h", "480": "8h", "720": "12h",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h", "H12": "12h",
    # days
    "1d": "1d", "D": "1d", "1D": "1d",
}

def _extract_symbol_tf_time(full_text: str):
    """
    Try to read SYMBOL, TF, DATETIME out of the OCR text that comes from a
    TradingView screenshot (English UI is assumed, but we allow some
    punctuation / locale variations).

    Returns: (symbol:str|None, timeframe:str|None, dt_iso:str|None)
    timeframe is normalized like: '15m','1h','4h','12h','1d', etc.
    dt_iso: 'YYYY-MM-DD HH:MM' when we can reconstruct it.
    """
    sym = None
    tf = None
    dt = None
    # normalize OCR text to reduce confusables and spacing noise
    t = _norm_text(full_text)
    # optional debug dump of the meta text
    _save_debug_text(t, tag="meta_raw")

    # Strong symbol hit anywhere: prioritize exchange-style tickers (…USDT/USD/USDC/BUSD)
    m_strong = re.search(r"\b([A-Z]{2,10})(USDT|USD|USDC|BUSD)\b", t)
    if m_strong:
        sym = (m_strong.group(1) + m_strong.group(2)).upper()

    # ---------- 1) Compact header in Data Window / with dashes ----------
    # e.g. "BNBUSDT · 15 · BINANCE" or "BNBUSDT-15-BINANCE"
    sep = r"[\s\.\-\/|·•]+"
    if sym is None or len(sym) < 6:
        m = re.search(
            rf"\b([A-Z0-9]{{2,15}}){sep}([A-Za-z0-9]{{1,4}}){sep}(BINANCE|BYBIT|OKX|COINBASE|KRAKEN)\b",
            t, re.I
        )
        if m:
            sym = m.group(1).upper()
            raw_tf = m.group(2)
            # '15' -> 15m ; '1h' -> 1h ; '240' -> 4h ; '60'->1h etc.
            if re.fullmatch(r"\d{1,3}", raw_tf):
                val = int(raw_tf)
                if val < 60:
                    tf = f"{val}m"
                elif val in (60, 120, 240, 360, 480, 720):
                    tf = {60:"1h",120:"2h",240:"4h",360:"6h",480:"8h",720:"12h"}[val]
            else:
                tf = _TF_MAP.get(raw_tf, raw_tf.lower() if raw_tf else None)

    # ---------- 2) Fallback: symbol anywhere ----------
    if sym is None:
        # vendor prefix: "BINANCE:BTCUSDT"
        m = re.search(r"\b[A-Z]+:([A-Z0-9]{2,20})\b", t)
        if m:
            sym = m.group(1).upper()
    if sym is None:
        # Plain pairs like BTCUSDT / ETHUSD / BNBPERP (optionally with slash)
        m = re.search(r"\b([A-Z]{2,10}/?[A-Z]{2,6})\b", t)
        if m:
            cand = m.group(1).replace('/', '').upper()
            # Avoid picking verbose asset names like TETHERUS; prefer exchange-style suffixes
            if any(cand.endswith(sfx) for sfx in ("USDT","USD","USDC","BUSD","PERP")) and len(cand) >= 6:
                sym = cand

    # ---------- 3) Timeframe: stronger fallbacks ----------
    if tf is None:
        # Again look for the separated header but without symbol (name header like "Binance Coin / TetherUS · 15 · BINANCE")
        m = re.search(rf"{sep}([0-9]{{1,3}}(?:m|h)?){sep}(?:BINANCE|BYBIT|OKX|COINBASE|KRAKEN)\b", t, re.I)
        if m:
            raw_tf = m.group(1)
            if raw_tf.isdigit():
                val = int(raw_tf)
                tf = f"{val}m" if val < 60 else {60:"1h",120:"2h",240:"4h",360:"6h",480:"8h",720:"12h"}.get(val)
            else:
                tf = _TF_MAP.get(raw_tf, raw_tf.lower())

    if tf is None:
        # explicit tokens present anywhere
        m = re.search(r"\b(1m|3m|5m|15m|30m|45m|1h|2h|4h|6h|8h|12h|1d|D|H1|H4|M5|M15|M30|60|120|240|360|480|720|15|30)\b", t, re.I)
        if m:
            key = m.group(1)
            tf = _TF_MAP.get(key, key.lower())

    if tf is None:
        # phrases like "15 min", "1 hour", "4 h", "1 day" (ru/en)
        m = re.search(r"\b(\d{1,3})\s*(мин|min|minutes?)\b", t, re.I)
        if m:
            tf = f"{int(m.group(1))}m"
        else:
            m = re.search(r"\b(\d{1,2})\s*(час|ч|hours?|hour|h)\b", t, re.I)
            if m:
                tf = f"{int(m.group(1))}h"
            else:
                m = re.search(r"\b(\d{1,2})\s*(д|days?|day|d)\b", t, re.I)
                if m:
                    tf = "1d" if int(m.group(1)) == 1 else f"{int(m.group(1))}d"

    # ---------- 4) Date/Time from Data Window ----------
    # Be robust: accept "Date\nFri 18-07-2025" / "Time\n08:45" OR inline variants,
    # and if labels are noisy, fall back to any dd-mm-yyyy + hh:mm pair seen in text.

    # First, try the canonical "Date ... / Time ..." labels (EN/RU)
    m_date = re.search(
        r"(?:^|\n)\s*(?:Date|Дата)\s*[: ]*\s*([A-Za-z]{3}\s+\d{1,2}[\-\./·•]\d{1,2}[\-\./·•]\d{2,4}|\d{1,2}[\-\./·•]\d{1,2}[\-\./·•]\d{2,4})",
        t, re.I
    )
    
    # Also try to find standalone dates like "Sun 18-05-2025"
    if not m_date:
        m_date = re.search(
            r"([A-Za-z]{3}\s+\d{1,2}[\-\./·•]\d{1,2}[\-\./·•]\d{2,4})",
            t, re.I
        )
        print(f"[OCR DEBUG] Standalone date search result: {m_date.group(1) if m_date else 'None'}")
    
    # If still no date, try DD-MM-YYYY format without day name
    if not m_date:
        m_date = re.search(r"(\d{1,2}[\-\./·•]\d{1,2}[\-\./·•]\d{4})", t)
        print(f"[OCR DEBUG] DD-MM-YYYY date search result: {m_date.group(1) if m_date else 'None'}")
    
    m_time = re.search(
        r"(?:^|\n)\s*(?:Time|Время)\s*[: ]*\s*(\d{1,2}[:\.·]\d{2})",
        t, re.I
    )
    
    # Also try to find standalone times like "12:00" 
    if not m_time:
        time_matches = re.findall(r"\b(\d{1,2}[:\.·]\d{2})\b", t)
        if time_matches:
            # Create a mock match object with the first valid time
            class MockMatch:
                def __init__(self, value):
                    self.value = value
                def group(self, n=1):
                    return self.value
            m_time = MockMatch(time_matches[0])

    def _pick_valid_hhmm(cands: list[str]) -> Optional[str]:
        """Return best HH:MM from candidates.
        Preference order:
          1) strictly valid HH:MM where minutes are one of {00,15,30,45};
          2) if there is a valid HH:MM but minutes are not on a 15-minute grid, **floor** minutes to the nearest 15-minute mark;
          3) if OCR swapped minutes/hours (e.g. 12:80 → 80:12), try the swap and apply the same rules.
        Always return a value aligned to a 15-minute grid.
        """
        def _norm_one(s: str) -> str:
            cc = re.sub(r"\s", "", s or "")
            # Map common separators to ':'
            cc = cc.replace(".", ":").replace("·", ":")
            # If OCR produced a hyphen between HH and MM (e.g. '08-45'), fix it *only* for HH-MM forms
            cc = re.sub(r"^(\d{1,2})-(\d{2})$", r"\1:\2", cc)
            return cc

        def _is_valid(s: str) -> bool:
            try:
                h, m = s.split(":")
                hi, mi = int(h), int(m)
                return 0 <= hi <= 23 and 0 <= mi <= 59
            except Exception:
                return False

        def _is_quarter(s: str) -> bool:
            try:
                mi = int(s.split(":")[1])
                return mi in {0, 15, 30, 45}
            except Exception:
                return False

        def _floor_quarter(s: str) -> Optional[str]:
            if not _is_valid(s):
                return None
            h, m = s.split(":")
            hi, mi = int(h), int(m)
            q = (mi // 15) * 15  # floor to 00/15/30/45
            result = f"{hi:02d}:{q:02d}"
            # Debug: print what we're converting
            if s != result:
                print(f"[OCR DEBUG] _floor_quarter: {s} -> {result}")
            return result

        norm: list[str] = []
        for c in cands:
            cc = _norm_one(c)
            if re.fullmatch(r"\d{1,2}:\d{2}", cc):
                norm.append(cc)

        # collect strictly valid
        valid = [cc for cc in norm if _is_valid(cc)]
        quarters = [cc for cc in valid if _is_quarter(cc)]
        
        # Debug: show what we found
        print(f"[OCR DEBUG] _pick_valid_hhmm: cands={cands}, norm={norm}, valid={valid}, quarters={quarters}")
        
        if quarters:
            result = quarters[0]
            print(f"[OCR DEBUG] _pick_valid_hhmm: returning quarter time: {result}")
            return result
        if valid:
            # align first valid time to quarter grid
            floored = _floor_quarter(valid[0])
            if floored:
                print(f"[OCR DEBUG] _pick_valid_hhmm: returning floored time: {valid[0]} -> {floored}")
                return floored

        # try swaps when minutes are out of range
        swapped: list[str] = []
        for cc in norm:
            m = re.match(r"^(\d{1,2}):(\d{2})$", cc)
            if not m:
                continue
            h, mm = m.group(1), m.group(2)
            try:
                hi, mi = int(h), int(mm)
            except Exception:
                continue
            if 0 <= hi <= 23 and mi >= 60:
                cand = f"{mi:02d}:{hi:02d}"
                if _is_valid(cand):
                    swapped.append(cand)
        if swapped:
            quarters_sw = [s for s in swapped if _is_quarter(s)]
            if quarters_sw:
                return quarters_sw[0]
            # align the first swapped valid to quarter grid
            for s in swapped:
                floored = _floor_quarter(s)
                if floored:
                    return floored

        return None

    def _canon_dt(dd:str, mm:str, yyyy:str, hhmm:str) -> str:
        if len(yyyy) == 2:
            yyyy = ("20" + yyyy)  # assume 20xx
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)} {hhmm}"

    def _ensure_dt_valid(dt_str: Optional[str]) -> Optional[str]:
        if not dt_str:
            return None
        s = dt_str.strip().replace("T", " ")
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})", s)
        if not m:
            return None
        yyyy, mm, dd, hh, mi = m.groups()
        try:
            _dt(int(yyyy), int(mm), int(dd), int(hh), int(mi))
            return f"{yyyy}-{mm}-{dd} {int(hh):02d}:{mi}"
        except Exception:
            return None

    print(f"[OCR DEBUG] Date match: {m_date.group(1) if m_date else 'None'}")
    print(f"[OCR DEBUG] Time match: {m_time.group(1) if m_time else 'None'}")
    
    if m_date and m_time:
        print(f"[OCR DEBUG] Processing date: {m_date.group(1)}")
        ddm = re.search(r"(\d{1,2})[\-\./·•](\d{1,2})[\-\./·•](\d{2,4})", m_date.group(1))
        if ddm:
            dd, mm, yyyy = ddm.group(1), ddm.group(2), ddm.group(3)
            print(f"[OCR DEBUG] Parsed date parts: dd={dd}, mm={mm}, yyyy={yyyy}")
            hhmm_raw = re.sub(r"[·.]", ":", m_time.group(1))
            print(f"[OCR DEBUG] Raw time: {hhmm_raw}")
            hhmm = _pick_valid_hhmm([hhmm_raw])
            print(f"[OCR DEBUG] Validated time: {hhmm}")
            if not hhmm:
                # fall back to any valid time in the entire text (prefer quarter-hour marks)
                times_all = re.findall(r"\b(\d{1,2}[:\.·]\d{2})\b", t)
                print(f"[OCR DEBUG] All times found: {times_all}")
                times_all = [re.sub(r"[·.]", ":", x) for x in times_all]
                hhmm = _pick_valid_hhmm(times_all) if times_all else None
            
            # Если время не найдено или невалидно, используем 12:00 по умолчанию
            if not hhmm:
                print("[OCR DEBUG] No valid time found, using default 12:00")
                hhmm = "12:00"
                
            if hhmm:
                dt = _ensure_dt_valid(_canon_dt(dd, mm, yyyy, hhmm))
                print(f"[OCR DEBUG] Final datetime: {dt}")
                if dt:
                    return sym, tf, dt
    else:
        # Labels may be missing; pick the first date+time found anywhere.
        date_hits = re.findall(r"\b(\d{1,2})[\-\./·•](\d{1,2})[\-\./·•](\d{2,4})\b", t)
        time_hits = re.findall(r"\b(\d{1,2}[:\.·]\d{2})\b", t)
        if date_hits and time_hits:
            dd, mm, yyyy = date_hits[0]
            hhmm = _pick_valid_hhmm([re.sub(r"[·.]", ":", x) for x in time_hits])
            if hhmm:
                dt = _ensure_dt_valid(_canon_dt(dd, mm, yyyy, hhmm))

    # If still nothing, try inline weekday + date + time (e.g., "Fri 18-07-2025 08:45")
    if dt is None:
        m_inline = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2}[\-\./·•]\d{1,2}[\-\./·•]\d{2,4})\s+(\d{1,2}[:\.·]\d{2})\b", t, re.I)
        if m_inline:
            ddm = re.search(r"(\d{1,2})[\-\./·•](\d{1,2})[\-\./·•](\d{2,4})", m_inline.group(2))
            if ddm:
                dd, mm, yyyy = ddm.group(1), ddm.group(2), ddm.group(3)
                hhmm = _pick_valid_hhmm([re.sub(r"[·.]", ":", m_inline.group(3))])
                if hhmm:
                    dt = _ensure_dt_valid(_canon_dt(dd, mm, yyyy, hhmm))

    # ---------- 4b) Additional generic patterns ----------
    if dt is None:
        dt_patterns = [
            r"\b(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)\b",
            r"\b(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})\b",
            r"\b(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})\b",
        ]
        for pat in dt_patterns:
            m = re.search(pat, t)
            if m:
                # Leave as-is; caller can post-normalize if needed
                dt = _ensure_dt_valid(m.group(1))
                break

    if sym:
        sym = sym.upper()
    if tf:
        tf = _TF_MAP.get(tf, tf)

    # Prefer exchange-style symbol if both styles appeared
    if sym and not any(sym.endswith(s) for s in ("USDT","USD","USDC","BUSD","PERP")):
        m_pref = re.search(r"\b([A-Z]{2,10})(USDT|USD|USDC|BUSD|PERP)\b", t)
        if m_pref:
            sym = (m_pref.group(1) + m_pref.group(2)).upper()

    if isinstance(dt, str) and not _ensure_dt_valid(dt):
        dt = None
    
    # Если не смогли распознать время, используем текущую дату
    if dt is None:
        from datetime import datetime
        dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return sym, tf, dt


# --------- text normalization & debug helpers ---------
_DEBUG_OCR_ENV = "DEBUG_OCR"

def _save_debug_text(txt: str, tag: str = "ocr") -> None:
    try:
        if os.environ.get(_DEBUG_OCR_ENV, "0").lower() in ("1", "true", "yes"):
            p = Path(f"/tmp/{tag}_text.txt")
            p.write_text(txt, encoding="utf-8")
    except Exception:
        pass

def _norm_text(t: str) -> str:
    """Normalize OCR text to reduce confusables and spacing noise."""
    t = unicodedata.normalize("NFC", t)
    # Map common Cyrillic lookalikes to Latin (OCR often mixes them)
    conf = {
        "о": "o", "О": "O",
        "с": "c", "С": "C",
        "е": "e", "Е": "E",
        "а": "a", "А": "A",
        "р": "p", "Р": "P",
        "х": "x", "Х": "X",
        "у": "y", "У": "Y",
        "к": "k", "К": "K",
        "в": "v", "В": "V",
        "н": "h", "Н": "H",
        "ы": "y", "Ы": "Y",
    }
    t = "".join(conf.get(ch, ch) for ch in t)
    # Normalize spaces / dashes / decimal commas
    t = t.replace("\u00A0", " ").replace("\u2009", " ").replace("\u2013", "-").replace("\u2014", "-")
    t = t.replace(",", ".")
    # extra ui glyphs and punctuation noise
    t = t.replace("©", " ").replace("™", " ")
    # some OCRs put weird mixed dashes or pipes
    t = t.replace("|", " ").replace("—", "-").replace("–", "-")
    # Collapse multiple spaces but keep newlines
    t = re.sub(r"[ \t]+", " ", t)
    return t

# --------- Robust OHLC parsing ---------
_LABELS = {
    "open": [
        r"\bopen\b", r"\bop?n\b", r"\bo\b", r"\b0\b", r"\bo\s*[:=]", r"\bopen?\s*[:=]",
    ],
    "high": [
        r"\bhigh\b", r"\bh\b", r"\bh\s*[:=]", r"\b[HН]\b", r"\bhi?gh?\b",
    ],
    "low": [
        r"\blow\b", r"\bl\b", r"\b[l1i]\b", r"\bl\s*[:=]", r"\blo?w\b",
    ],
    "close": [
        r"\bclose\b", r"\bc\b", r"\b[CС]\b", r"\bc\s*[:=]", r"\bclo?se?\b",
    ],
}

_NUM = r"([-+]?\d+(?:\.?\d+)?)"
_NUM_FLEX = r"([-+]?\d{1,3}(?:[\s,]?\d{3})*(?:[\.,]\d+)?|[-+]?\d+(?:[\.,]\d+)?)"

def _parse_ohlc_from_text(text: str) -> Tuple[float, float, float, float]:
    """Robustly parse OHLC from arbitrary OCR text.
    Strategy:
      1) Normalize text (confusables, spaces, decimals).
      2) Collect label→value by scanning for each alias.
      3) If still missing, try block order O/H/L/C with arbitrary spacing/newlines.
      4) If still missing, raise.
    """
    t = _norm_text(text)
    t = t.replace("：", ":").replace("=", ":")
    # 1) Direct label-value scan (accept line/space/newline separation)
    found: Dict[str, float] = {}
    for key, aliases in _LABELS.items():
        for alias in aliases:
            pat = re.compile(rf"{alias}[\s\n\r]*[:=]?[\s\n\r]*{_NUM_FLEX}", re.I)
            m1 = pat.search(t)
            if m1:
                try:
                    found[key] = float(m1.group(1).replace(' ', '').replace(',', '.'))
                    break
                except Exception:
                    continue

    if all(k in found for k in ("open","high","low","close")):
        return found["open"], found["high"], found["low"], found["close"]

    # 2) Block form like: O 746.9 H 748.3 L 746.1 C 747.2 (with newlines allowed)
    pat_block = re.compile(
        rf"[O0]\s*[:=]?\s*{_NUM_FLEX}.*?[HН]\s*[:=]?\s*{_NUM_FLEX}.*?[L1I]\s*[:=]?\s*{_NUM_FLEX}.*?[CС]\s*[:=]?\s*{_NUM_FLEX}",
        re.I | re.S,
    )
    m2 = pat_block.search(t)
    if m2:
        nums = re.findall(_NUM_FLEX, m2.group(0))
        if len(nums) >= 4:
            vals = [float(x.replace(' ', '').replace(',', '.')) for x in nums[:4]]
            o, h, l, c = vals
            return o, h, l, c

    # 3) Worded block: Open ... High ... Low ... Close ...
    pat_wh = re.compile(
        rf"open\s*[:=]?\s*{_NUM_FLEX}.*?high\s*[:=]?\s*{_NUM_FLEX}.*?low\s*[:=]?\s*{_NUM_FLEX}.*?close\s*[:=]?\s*{_NUM_FLEX}",
        re.I | re.S,
    )
    m3 = pat_wh.search(t)
    if m3:
        nums = re.findall(_NUM_FLEX, m3.group(0))
        if len(nums) >= 4:
            vals = [float(x.replace(' ', '').replace(',', '.')) for x in nums[:4]]
            o, h, l, c = vals
            return o, h, l, c

    # 3b) Compact tokens like: O 746.9, H 748.3, L 746.3, C 747.8
    m4 = re.search(rf"\b[O0]\b\s*{_NUM_FLEX}.*?\b[HН]\b\s*{_NUM_FLEX}.*?\b[L1I]\b\s*{_NUM_FLEX}.*?\b[CС]\b\s*{_NUM_FLEX}", t, re.I | re.S)
    if m4:
        nums = re.findall(_NUM_FLEX, m4.group(0))
        if len(nums) >= 4:
            o, h, l, c = [float(n.replace(' ', '').replace(',', '.')) for n in nums[:4]]
            return o, h, l, c

    # 4) Give a helpful debug dump
    _save_debug_text(t, tag="ocr_last")
    raise ValueError("Could not find OHLC in OCR text")

def _parse_ohlc_via_tokens(img: "Image.Image", tess_langs: list[str]) -> Tuple[float, float, float, float]:
    """Fallback: use pytesseract word boxes to find labels and the nearest number.
    We scan per-word tokens and map the next numeric token near each label.
    """
    if pytesseract is None:
        raise ValueError("pytesseract unavailable")

    # Prefer a clean grayscale for OCR tokenization
    g = img.convert("L")
    # light binarization to improve contrast on light themes
    try:
        bw = g.point(lambda x: 255 if x > 200 else (0 if x < 120 else 200))
    except Exception:
        bw = g

    try:
        data = pytesseract.image_to_data(bw, lang="+".join(tess_langs) if tess_langs else "eng",
                                         output_type=pytesseract.Output.DICT)
    except Exception as e:
        raise ValueError(f"tesseract image_to_data failed: {e}")

    words = data.get("text", []) or []
    # Normalize tokens
    tokens: list[str] = []
    for w in words:
        w = (w or "").strip()
        if not w:
            continue
        # unify punctuation
        w = w.replace(",", ".").replace(":", ":")
        tokens.append(w)

    def _is_num(tok: str) -> bool:
        return bool(re.fullmatch(_NUM_FLEX, tok))

    # label aliases we will accept in token form
    lab_aliases = {
        "open": {"open", "o", "0"},
        "high": {"high", "h", "H", "Н"},
        "low": {"low", "l", "L", "1", "I"},
        "close": {"close", "c", "C", "С"},
    }

    found: Dict[str, float] = {}
    n = len(tokens)
    for i, t in enumerate(tokens):
        tl = t.lower()
        for key, aliases in lab_aliases.items():
            if tl in {a.lower() for a in aliases} or re.fullmatch(rf"{key}[:=]?", tl, re.I):
                # look ahead a few tokens for the first numeric value
                for j in range(i + 1, min(i + 6, n)):
                    cand = tokens[j].replace(" ", "")
                    if _is_num(cand):
                        try:
                            found[key] = float(re.sub(r"[\s,]", "", cand).replace(",", "."))
                            break
                        except Exception:
                            continue
                break

    if all(k in found for k in ("open", "high", "low", "close")):
        return found["open"], found["high"], found["low"], found["close"]

    # As a last-ditch attempt, find a run of four numeric tokens near the area where labels were seen
    nums = [float(re.sub(r"[\s,]", "", t).replace(",", ".")) for t in tokens if _is_num(t)]
    if len(nums) >= 4:
        return nums[0], nums[1], nums[2], nums[3]

    raise ValueError("token scan failed to find OHLC")

def _find_green_highlights(img) -> List[Dict[str, Any]]:
    """
    Находит зеленые прямоугольные выделения на скриншоте TradingView.
    Это маркировка пользователем FIX свечи.
    
    Returns:
        List[Dict] с координатами найденных зеленых областей:
        [{'x': int, 'y': int, 'width': int, 'height': int, 'center_x': int, 'center_y': int}]
    """
    try:
        import numpy as np
        from PIL import ImageFilter
        
        # Конвертируем в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Конвертируем в numpy array
        img_array = np.array(img)
        
        # Определяем диапазон зеленого цвета (HSV более точно)
        img_hsv = img.convert('HSV')
        hsv_array = np.array(img_hsv)
        
        # Диапазон для зеленого цвета в HSV
        # H: 60-120 (зеленый), S: 100-255 (насыщенность), V: 100-255 (яркость)
        h, s, v = hsv_array[:,:,0], hsv_array[:,:,1], hsv_array[:,:,2]
        
        # Маска для зеленых пикселей
        green_mask = (
            (h >= 60) & (h <= 120) &    # Зеленый оттенок
            (s >= 100) &                # Достаточно насыщенный  
            (v >= 100)                  # Достаточно яркий
        )
        
        # Находим контуры зеленых областей
        from scipy import ndimage
        labeled, num_features = ndimage.label(green_mask)
        
        green_boxes = []
        for i in range(1, num_features + 1):
            # Координаты пикселей этого объекта
            coords = np.where(labeled == i)
            
            if len(coords[0]) < 50:  # Слишком маленькая область
                continue
                
            y_min, y_max = coords[0].min(), coords[0].max()
            x_min, x_max = coords[1].min(), coords[1].max()
            
            width = x_max - x_min
            height = y_max - y_min
            
            # Фильтруем по размеру - ищем прямоугольные выделения
            if width < 20 or height < 20:  # Слишком маленькие
                continue
            if width > img.width * 0.5 or height > img.height * 0.5:  # Слишком большие  
                continue
                
            green_boxes.append({
                'x': int(x_min),
                'y': int(y_min), 
                'width': int(width),
                'height': int(height),
                'center_x': int(x_min + width // 2),
                'center_y': int(y_min + height // 2),
                'area': int(width * height)
            })
            
        # Сортируем по размеру (самые большие сначала)
        green_boxes.sort(key=lambda x: x['area'], reverse=True)
        
        print(f"[OCR DEBUG] Found {len(green_boxes)} green highlights")
        for box in green_boxes:
            print(f"[OCR DEBUG] Green box: center=({box['center_x']}, {box['center_y']}), size={box['width']}x{box['height']}")
            
        return green_boxes
        
    except Exception as e:
        print(f"[OCR DEBUG] Green highlight detection failed: {e}")
        return []


def extract_ohlc_from_image(image_path: str, lang: Optional[object] = 'en', **_ignored) -> Dict[str, Any]:
    # noqa: ARG002 — extra kwargs are accepted for compatibility
    """
    Reads a TradingView screenshot, performs OCR, and extracts:
      - OHLC numbers
      - symbol, timeframe, datetime (best-effort)
    Args:
        image_path: path to PNG/JPG.
        lang: OCR languages; string like 'en' or 'en,ru' or list ['en','ru'].
              Extra keyword args are accepted and ignored for compatibility.
    Returns:
        dict with keys: 'open','high','low','close','symbol','timeframe','datetime','raw_text'.
    """
    image_path = os.path.expanduser(str(image_path))
    p = Path(image_path)
    # --- normalize language argument for OCR backends ---
    # accepts: 'en' or 'en,ru' or ['en', 'ru']
    if isinstance(lang, str):
        langs = [s.strip().lower() for s in re.split(r"[,\s]+", lang) if s.strip()]
    else:
        langs = [str(x).lower() for x in (lang or ['en'])]
    if not langs:
        langs = ['en']

    # tesseract uses different codes (eng, rus, ...)
    _TESS_LANG_MAP = {'en': 'eng', 'ru': 'rus'}
    tess_langs = [_TESS_LANG_MAP.get(x, x) for x in langs]

    if not p.exists():
        raise FileNotFoundError(str(p))
    if Image is None:
        raise RuntimeError("PIL is required to open images")

    img = Image.open(p)
    raw_text = ""

    # 1) Try EasyOCR first (robust to UI fonts). It may be heavy to import on first run.
    if easyocr is not None:
        try:
            reader = easyocr.Reader(langs, gpu=False)
            lines = reader.readtext(img, detail=0, paragraph=True)
            raw_text = "\n".join(lines)
        except Exception:
            pass

    # 2) Fallback to Tesseract if EasyOCR text is empty
    if (not raw_text) and (pytesseract is not None):
        try:
            raw_text = pytesseract.image_to_string(img, lang="+".join(tess_langs))
        except Exception:
            pass

    if not raw_text:
        raise RuntimeError("OCR backends produced empty text")

    _save_debug_text(raw_text, tag="ocr_raw")
    print(f"[OCR DEBUG] raw_text: {repr(raw_text[:500])}")  # Debug what OCR sees

    # Parse values from normalized text; if that fails, use token-level fallback
    try:
        o, h, l, c = _parse_ohlc_from_text(raw_text)
    except Exception:
        # fallback to word-box driven parsing
        try:
            o, h, l, c = _parse_ohlc_via_tokens(img, tess_langs)
        except Exception as e:
            _save_debug_text(raw_text, tag="ocr_last")
            raise ValueError(f"Could not find OHLC in OCR text (tokens fallback failed): {e}")

    sym, tf, dt = _extract_symbol_tf_time(raw_text)

    # Добавляем поиск зеленых выделений (маркировка FIX свечи)
    green_boxes = _find_green_highlights(img)
    
    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "symbol": sym,
        "timeframe": tf,
        "datetime": dt,
        "raw_text": raw_text,
        "green_highlights": green_boxes,  # Координаты зеленых выделений
    }

__all__ = [
    "extract_ohlc_from_image",
    "_extract_symbol_tf_time",
]