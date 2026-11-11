# -*- coding: utf-8 -*-
"""Qurilish Radar — manbalar (yangi qurilish/novostroyka topish).

Har bir manba funksiyasi quyidagi ko'rinishdagi obyektlar ro'yxatini qaytaradi:
  {kalit, manba, nom, url, joy, quruvchi, holat, sana, rasm}
kalit — takrorlanmaslik uchun noyob belgi (odatda url).

Eslatma: bu kod Railway (to'liq internet)da ishlaydi. Saytlar o'zgarishi mumkin,
shuning uchun har bir manba alohida try/except bilan o'raladi — biri ishlamasa,
boshqalari ishlayveradi. /test buyrug'i har manba nima qaytarganini ko'rsatadi.
"""
import logging
import hashlib
import re

import requests

log = logging.getLogger("manbalar")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEAD = {"User-Agent": UA, "Accept-Language": "uz,ru;q=0.9,en;q=0.8"}

# Qurilishga oid kalit so'zlar (o'zbek + rus)
KALIT_SOZLAR = [
    "turar-joy majmua", "turar joy majmua", "tjm ", "ko'p qavatli", "kop qavatli",
    "novostroyka", "novostroyki", "uy-joy qurilish", "uy joy qurilish",
    "qurilish boshland", "qad rostla", "ko'chmas mulk qurilish",
    "жилой комплекс", "жилого комплекса", "новостройк", "многоэтажн",
    "строительство жил", "возведен", "жк ",
]

# Yangilik RSS lentalari (har sayt uchun bir nechta ehtimoliy manzil — ishlaganini oladi)
RSS_FEEDS = [
    "https://www.gazeta.uz/uz/rss/",
    "https://www.gazeta.uz/rss/",
    "https://www.spot.uz/uz/rss/",
    "https://kun.uz/uz/rss",
    "https://kun.uz/rss",
    "https://uza.uz/uz/rss",
]


def _kalit(url, nom=""):
    base = (url or "") + "|" + (nom or "")
    return hashlib.md5(base.encode("utf-8", "ignore")).hexdigest()[:16]


def _qurilishga_oidmi(matn):
    m = (matn or "").lower()
    return any(k in m for k in KALIT_SOZLAR)


# ---------------- Manba 1: Yangilik RSS lentalari ----------------
def rss_scan():
    """Rasmiy/ommaviy yangiliklardan qurilishga oid xabarlarni oladi."""
    try:
        import feedparser
    except Exception:
        log.warning("feedparser yo'q")
        return []
    out = []
    seen_feed = set()
    for url in RSS_FEEDS:
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        if host in seen_feed:
            continue  # bir saytdan bitta ishlagan lenta yetarli
        try:
            r = requests.get(url, headers=HEAD, timeout=15)
            if r.status_code != 200 or not r.content:
                continue
            feed = feedparser.parse(r.content)
            if not feed.entries:
                continue
            seen_feed.add(host)
            for e in feed.entries[:40]:
                nom = (getattr(e, "title", "") or "").strip()
                xul = (getattr(e, "summary", "") or "")
                link = (getattr(e, "link", "") or "").strip()
                if not nom or not link:
                    continue
                if not _qurilishga_oidmi(nom + " " + xul):
                    continue
                sana = (getattr(e, "published", "") or getattr(e, "updated", "") or "")
                rasm = ""
                try:
                    if getattr(e, "media_content", None):
                        rasm = e.media_content[0].get("url", "")
                    elif getattr(e, "links", None):
                        for l in e.links:
                            if "image" in (l.get("type") or ""):
                                rasm = l.get("href", "")
                except Exception:
                    pass
                out.append({
                    "kalit": _kalit(link, nom), "manba": host, "nom": nom, "url": link,
                    "joy": "", "quruvchi": "", "holat": "yangilik", "sana": sana, "rasm": rasm,
                })
        except Exception as ex:
            log.info("RSS xato %s: %s", url, ex)
    return out


# ---------------- Manba 2: uysot.uz (novostroyka + quruvchi) ----------------
def uysot_scan():
    """uysot.uz sahifasidan novostroyka ro'yxatini olishga urinadi (sahifaga joylangan JSON).
    Sayt tузилishi o'zgaruvchan — ishlamasa bo'sh qaytadi (keyin moslaymiz)."""
    out = []
    urls = [
        "https://uysot.uz/uz/uzbekistan/novostroyki",
        "https://uysot.uz/uzbekistan/novostroyki",
        "https://uysot.uz/gorod-tashkent/novostroyki",
    ]
    import json as _json
    for url in urls:
        try:
            r = requests.get(url, headers=HEAD, timeout=20)
            if r.status_code != 200 or not r.text:
                continue
            html = r.text
            # Next.js sahifalari ma'lumotni __NEXT_DATA__ ichida saqlaydi
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if not m:
                continue
            data = _json.loads(m.group(1))
            # Strukturani aniq bilmaymiz — "novostroyki/complexes/items" kabi kalitlarni qidiramiz
            topildi = _json_dan_obyektlar(data)
            for it in topildi:
                nom = it.get("name") or it.get("title") or ""
                if not nom:
                    continue
                slug = it.get("slug") or it.get("id") or ""
                link = "https://uysot.uz/uz/novostroyki/%s" % slug if slug else url
                joy = it.get("district") or it.get("region") or it.get("address") or ""
                dev = ""
                d = it.get("builder") or it.get("developer") or it.get("zastroyshik")
                if isinstance(d, dict):
                    dev = d.get("name") or ""
                elif isinstance(d, str):
                    dev = d
                holat = it.get("status") or it.get("state") or ""
                out.append({
                    "kalit": _kalit(link, nom), "manba": "uysot.uz", "nom": nom, "url": link,
                    "joy": str(joy), "quruvchi": str(dev), "holat": str(holat),
                    "sana": str(it.get("deadline") or it.get("completion") or ""), "rasm": "",
                })
            if out:
                break  # bitta ishlagan url yetarli
        except Exception as ex:
            log.info("uysot xato %s: %s", url, ex)
    return out


def _json_dan_obyektlar(data, chuqur=0):
    """__NEXT_DATA__ ichidan obyektga o'xshash (name+slug/address bor) elementlarni qidiradi."""
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
    """Barcha manbalardan yig'adi. Qaytadi: (obyektlar, hisobot_dict)."""
    hisobot = {}
    natija = []
    for nom, fn in (("RSS yangiliklar", rss_scan), ("uysot.uz", uysot_scan)):
        try:
            items = fn() or []
            hisobot[nom] = len(items)
            natija += items
        except Exception as ex:
            hisobot[nom] = "xato: %s" % type(ex).__name__
            log.exception("manba %s xato", nom)
    # takror url larni birlashtiramiz
    korilgan = set()
    uniq = []
    for it in natija:
        if it["kalit"] in korilgan:
            continue
        korilgan.add(it["kalit"])
        uniq.append(it)
    return uniq, hisobot
