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
def uysot_scan():
    items, detail = [], []
    import json as _json
    for url in ["https://uysot.uz/uz/uzbekistan/novostroyki",
                "https://uysot.uz/uzbekistan/novostroyki"]:
        try:
            r = requests.get(url, headers=HEAD, timeout=20)
            st = r.status_code
            if st != 200 or not r.text:
                detail.append("uysot=%s" % st)
                continue
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            if not m:
                detail.append("uysot=200,json=yo'q")
                continue
            data = _json.loads(m.group(1))
            objs = _json_dan_obyektlar(data)
            for it in objs:
                nom = it.get("name") or it.get("title") or ""
                if not nom:
                    continue
                slug = it.get("slug") or it.get("id") or ""
                link = "https://uysot.uz/uz/novostroyki/%s" % slug if slug else url
                d = it.get("builder") or it.get("developer") or ""
                dev = d.get("name") if isinstance(d, dict) else (d if isinstance(d, str) else "")
                items.append({"kalit": _kalit(link, nom), "manba": "uysot.uz", "nom": nom,
                              "url": link,
                              "joy": str(it.get("district") or it.get("region") or it.get("address") or ""),
                              "quruvchi": str(dev or ""),
                              "holat": str(it.get("status") or it.get("state") or ""),
                              "sana": str(it.get("deadline") or ""), "rasm": ""})
            detail.append("uysot=200,obj=%d" % len(objs))
            break
        except Exception:
            detail.append("uysot=xato")
    return items, " | ".join(detail)


def _json_dan_obyektlar(data, chuqur=0):
    topildi = []
    if chuqur > 8:
        return topildi
    if isinstance(data, dict):
        kalitlar = set(k.lower() for k in data.keys())
        if ("name" in kalitlar or "title" in kalitlar) and \
           ("slug" in kalitlar or "address" in kalitlar or "district" in kalitlar or "builder" in kalitlar):
            topildi.append(data)
        for v in data.values():
            topildi += _json_dan_obyektlar(v, chuqur + 1)
    elif isinstance(data, list):
        for v in data:
            topildi += _json_dan_obyektlar(v, chuqur + 1)
    return topildi


# ---------------- Hammasi ----------------
def hammasi():
    """Qaytadi: (uniq_items, hisobot_dict). hisobot — har manba diagnostikasi."""
    hisobot, natija = {}, []
    for nom, fn in (("News (Google)", gnews_scan), ("RSS", rss_scan), ("uysot", uysot_scan)):
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
