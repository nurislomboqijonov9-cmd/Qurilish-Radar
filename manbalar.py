# -*- coding: utf-8 -*-
"""Qurilish Radar — manbalar (yangi qurilish/novostroyka topish).

Har bir manba (items, detail) qaytaradi:
  items  — [{kalit, manba, nom, url, joy, quruvchi, holat, sana, rasm}, ...]
  detail — diagnostika satri (nima topildi / qanday status), /test ko'rsatadi.

Railway (to'liq internet)da ishlaydi. Har manba try/except bilan — biri
ishlamasa boshqasi ishlayveradi.
"""
import logging
import hashlib
import re
import urllib.parse

import requests

log = logging.getLogger("manbalar")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEAD = {"User-Agent": UA, "Accept-Language": "uz,ru;q=0.9,en;q=0.8"}


def _kalit(url, nom=""):
    base = (url or "") + "|" + (nom or "")
    return hashlib.md5(base.encode("utf-8", "ignore")).hexdigest()[:16]


def _parse_feed(content):
    try:
        import feedparser
        return feedparser.parse(content)
    except Exception:
        return None


# ---------------- Manba 1: Google News RSS (eng ishonchli) ----------------
# Qurilish so'zlari bo'yicha qidiradi — serverdan bemalol ishlaydi.
GNEWS_QUERIES = [
    ("uz", "turar-joy majmuasi qurilishi O'zbekiston"),
    ("uz", "yangi novostroyka Toshkent qurilish boshlandi"),
    ("ru", "жилой комплекс строительство Ташкент"),
    ("ru", "новостройка Узбекистан застройщик строится"),
]


def _gnews_url(lang, q):
    return ("https://news.google.com/rss/search?q=%s&hl=%s&gl=UZ&ceid=UZ:%s"
            % (urllib.parse.quote(q), lang, lang))


def gnews_scan():
    items, detail = [], []
    for lang, q in GNEWS_QUERIES:
        url = _gnews_url(lang, q)
        try:
            r = requests.get(url, headers=HEAD, timeout=15)
            if r.status_code != 200 or not r.content:
                detail.append("%s=%s" % (q[:10], r.status_code))
                continue
            feed = _parse_feed(r.content)
            n = 0
            for e in (feed.entries[:25] if feed else []):
                nom = (getattr(e, "title", "") or "").strip()
                link = (getattr(e, "link", "") or "").strip()
                if not nom or not link:
                    continue
                items.append({"kalit": _kalit(link, nom), "manba": "news", "nom": nom,
                              "url": link, "joy": "", "quruvchi": "", "holat": "yangilik",
                              "sana": getattr(e, "published", "") or "", "rasm": ""})
                n += 1
            detail.append("%s=%d" % (q[:10], n))
        except Exception:
            detail.append("%s=xato" % q[:10])
    return items, " | ".join(detail)


# ---------------- Manba 2: To'g'ridan-to'g'ri yangilik RSS lentalari ----------------
KALIT_SOZLAR = [
    "turar-joy majmua", "turar joy majmua", "tjm ", "ko'p qavatli", "kop qavatli",
    "novostroyka", "novostroyki", "uy-joy qurilish", "uy joy qurilish",
    "qurilish boshland", "qad rostla", "жилой комплекс", "новостройк",
    "многоэтажн", "застройщик", "возвед",
]
RSS_FEEDS = [
    "https://www.gazeta.uz/uz/rss/",
    "https://kun.uz/uz/rss",
    "https://www.spot.uz/uz/rss/",
]


def _qurilishga_oidmi(matn):
    m = (matn or "").lower()
    return any(k in m for k in KALIT_SOZLAR)


def rss_scan():
    items, detail = [], []
    for url in RSS_FEEDS:
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        try:
            r = requests.get(url, headers=HEAD, timeout=15)
            if r.status_code != 200 or not r.content:
                detail.append("%s=%s" % (host, r.status_code))
                continue
            feed = _parse_feed(r.content)
            jami = len(feed.entries) if feed else 0
            n = 0
            for e in (feed.entries[:50] if feed else []):
                nom = (getattr(e, "title", "") or "").strip()
                xul = getattr(e, "summary", "") or ""
                link = (getattr(e, "link", "") or "").strip()
                if not nom or not link or not _qurilishga_oidmi(nom + " " + xul):
                    continue
                items.append({"kalit": _kalit(link, nom), "manba": host, "nom": nom,
                              "url": link, "joy": "", "quruvchi": "", "holat": "yangilik",
                              "sana": getattr(e, "published", "") or "", "rasm": ""})
                n += 1
            detail.append("%s=%d/%d" % (host, n, jami))
        except Exception:
            detail.append("%s=xato" % host)
    return items, " | ".join(detail)


# ---------------- Manba 3: uysot.uz (novostroyka + quruvchi) ----------------
def _text(v):
    """str / {uz,ru} / {name:...} dan matn chiqaradi."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        for k in ("uz", "name", "title", "ru", "en"):
            if v.get(k):
                return _text(v[k])
    return ""


def _kompleks_obj(c):
    """uysot kompleks elementidan bizning obyekt (yoki None)."""
    if not isinstance(c, dict):
        return None
    nom = _text(c.get("name") or c.get("title"))
    if not nom:
        return None
    slug = c.get("slug") or c.get("id") or ""
    link = "https://uysot.uz/uz/novostroyki/%s" % slug if slug else "https://uysot.uz"
    dev = _text(c.get("builder") or c.get("developer") or c.get("company") or c.get("zastroyshik"))
    dist = _text(c.get("district") or c.get("city"))
    reg = _text(c.get("region"))
    addr = _text(c.get("address"))
    joy = ", ".join(x for x in (dist, reg) if x) or addr
    holat = _text(c.get("status") or c.get("build_status") or c.get("state"))
    sana = _text(c.get("deadline") or c.get("date_build") or c.get("build_year") or c.get("quarter"))
    narx = _text(c.get("min_price") or c.get("price_from") or c.get("price"))
    if narx and "narx" not in holat.lower():
        holat = (holat + (" · " if holat else "") + "narx: %s" % narx)
    rasm = ""
    imgs = c.get("images") or c.get("photo") or c.get("logo")
    if isinstance(imgs, list) and imgs:
        rasm = _text(imgs[0]) if isinstance(imgs[0], (str, dict)) else ""
    elif isinstance(imgs, str):
        rasm = imgs
    return {"kalit": _kalit(link, nom), "manba": "uysot.uz", "nom": nom, "url": link,
            "joy": joy, "quruvchi": dev, "holat": holat, "sana": sana, "rasm": rasm}


def uysot_scan():
    items, detail = [], []
    import json as _json
    for url in ["https://uysot.uz/uz/uzbekistan/novostroyki",
                "https://uysot.uz/uz/gorod-tashkent/novostroyki",
                "https://uysot.uz/uzbekistan/novostroyki"]:
        try:
            r = requests.get(url, headers=HEAD, timeout=20)
            if r.status_code != 200 or not r.text:
                detail.append("%s" % r.status_code)
                continue
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            if not m:
                detail.append("json yo'q")
                continue
            data = _json.loads(m.group(1))
            qs = (((data.get("props") or {}).get("pageProps") or {}).get("dehydratedState") or {}).get("queries") or []
            # residential_complexes query'ini topamiz
            cq = None
            for q in qs:
                key = q.get("queryKey")
                keys = key if isinstance(key, list) else [key]
                if any("residential_complex" in str(x).lower() or "complex" in str(x).lower() for x in keys):
                    cq = q
                    break
            if not cq:
                detail.append("complex query yo'q")
                continue
            d = (cq.get("state") or {}).get("data")
            pages = d.get("pages") if isinstance(d, dict) else (d if isinstance(d, list) else [])
            komplekslar = []
            for pg in (pages or []):
                if isinstance(pg, list):
                    komplekslar += pg
                elif isinstance(pg, dict):
                    qoshildi = False
                    for sk in ("data", "results", "items", "complexes", "novostroyki", "list"):
                        if isinstance(pg.get(sk), list):
                            komplekslar += pg[sk]
                            qoshildi = True
                            break
                    if not qoshildi and pg.get("name"):
                        komplekslar.append(pg)
            n = 0
            namuna_keys = ""
            for c in komplekslar:
                if isinstance(c, dict) and not namuna_keys:
                    namuna_keys = ",".join(list(c.keys())[:12])
                obj = _kompleks_obj(c)
                if obj:
                    items.append(obj)
                    n += 1
            detail.append("complex=%d [%s]" % (n, namuna_keys))
            break
        except Exception as ex:
            detail.append("xato:%s" % type(ex).__name__)
    return items, " | ".join(detail)


def uysot_struktura():
    """Diagnostika: uysot sahifasidagi __NEXT_DATA__ tuzilishini ko'rsatadi,
    shunda to'g'ri parser yozamiz."""
    import json as _json
    out = []
    for url in ["https://uysot.uz/uz/uzbekistan/novostroyki",
                "https://uysot.uz/uzbekistan/novostroyki",
                "https://uysot.uz/en/uzbekistan/novostroyki"]:
        try:
            r = requests.get(url, headers=HEAD, timeout=20)
            out.append("URL: %s -> %s (%d bayt)" % (url.split("uysot.uz")[1], r.status_code, len(r.text or "")))
            if r.status_code != 200 or not r.text:
                continue
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            if not m:
                out.append("  __NEXT_DATA__ YO'Q. 'novostroyki' so'zi bor: %s" % ("novostroyki" in r.text))
                # boshqa katta JSON bormi?
                for pat in ("self.__next_f", "application/json", "window.__NUXT__"):
                    if pat in r.text:
                        out.append("  topildi belgisi: %s" % pat)
                continue
            data = _json.loads(m.group(1))
            pp = (data.get("props") or {}).get("pageProps") or {}
            qs = ((pp.get("dehydratedState") or {}).get("queries")) or []
            out.append("  queries soni: %d" % len(qs))
            for i, q in enumerate(qs):
                key = str(q.get("queryKey"))[:46]
                d = (q.get("state") or {}).get("data")
                if isinstance(d, list):
                    ek = list(d[0].keys())[:14] if (d and isinstance(d[0], dict)) else "-"
                    out.append("  q[%d] %s -> list[%d] keys=%s" % (i, key, len(d), ek))
                elif isinstance(d, dict):
                    sub = None
                    for sk in ("data", "results", "items", "complexes", "novostroyki", "list"):
                        v = d.get(sk)
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            sub = (sk, v)
                            break
                    if sub:
                        out.append("  q[%d] %s -> {%s} | %s:list[%d] keys=%s"
                                   % (i, key, ",".join(list(d.keys())[:6]), sub[0], len(sub[1]),
                                      list(sub[1][0].keys())[:16]))
                    else:
                        out.append("  q[%d] %s -> dict{%s}" % (i, key, ",".join(list(d.keys())[:10])))
                else:
                    out.append("  q[%d] %s -> %s" % (i, key, type(d).__name__))
            return "\n".join(out)[:3800]
        except Exception as ex:
            out.append("  xato: %s" % ex)
    return "\n".join(out)[:3800]


_LOYIHA_BELGI = {"builder", "developer", "zastroyshik", "price", "min_price", "minprice",
                 "district", "address", "region", "rooms", "deadline", "complex", "metros",
                 "price_from", "latitude", "longitude", "photo", "images"}


def _loyiha_royxatlari(data, yol="", chuqur=0, topildi=None):
    """name/title bor VA quruvchi/narx/joy kabi belgili elementlardan iborat ro'yxatlar."""
    if topildi is None:
        topildi = []
    if chuqur > 9:
        return topildi
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            ks = set(k.lower() for k in data[0].keys())
            if ("name" in ks or "title" in ks) and (ks & _LOYIHA_BELGI):
                nm = data[0].get("name") or data[0].get("title")
                topildi.append((yol, len(data), list(data[0].keys())[:24], str(nm)[:40]))
        for i, v in enumerate(data[:2]):
            _loyiha_royxatlari(v, "%s[%d]" % (yol, i), chuqur + 1, topildi)
    elif isinstance(data, dict):
        for k, v in data.items():
            _loyiha_royxatlari(v, "%s.%s" % (yol, k), chuqur + 1, topildi)
    return topildi


# ---------------- Hammasi ----------------
def hammasi():
    """Qaytadi: (uniq_items, hisobot_dict). hisobot — har manba diagnostikasi.
    Hozircha faqat haqiqiy loyiha manbasi (uysot). Yangilik manbalari o'chirilgan
    (ular maqola edi, loyiha emas)."""
    hisobot, natija = {}, []
    for nom, fn in (("uysot", uysot_scan),):
        try:
            items, detail = fn()
            natija += items
            hisobot[nom] = "%d ta [%s]" % (len(items), detail or "—")
        except Exception as ex:
            hisobot[nom] = "xato: %s" % type(ex).__name__
            log.exception("manba %s", nom)
    korilgan, uniq = set(), []
    for it in natija:
        if it["kalit"] in korilgan:
            continue
        korilgan.add(it["kalit"])
        uniq.append(it)
    return uniq, hisobot
