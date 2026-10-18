# -*- coding: utf-8 -*-
"""文獻逐筆核對：DOI → Crossref 書目逐欄比對；無 DOI 之網址檢查可否開啟；內文引用 ↔ 文獻清單雙向核對。
輸出 refcheck.json。用法：python refcheck.py"""
import difflib
import json
import re
import time
import unicodedata
import urllib.request

UA = {"User-Agent": "kidney-cause-audit/1.0 (mailto:research@example.org)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


docs = {n: json.load(open(f"{n}.json", encoding="utf-8")) for n in ["B_fair", "A_tisf"]}
allrefs = {}
for n, J in docs.items():
    for r in J["refs"]:
        if r in ("一、參考文獻",) or len(r) < 30:
            continue
        allrefs.setdefault(r, []).append(n)

out = []
cache = {}
for ref, where in allrefs.items():
    rec = dict(ref=ref, docs=where, issues=[])
    m = re.search(r"https?://doi\.org/(\S+?)\.?$", ref)
    ym = re.search(r"\((\d{4})[a-z]?(?:, [^)]*)?\)", ref)
    rec["year_cited"] = ym.group(1) if ym else None
    if m:
        doi = m.group(1)
        rec["doi"] = doi
        try:
            if doi not in cache:
                st, b = get("https://api.crossref.org/works/" + urllib.request.quote(doi, safe="/"))
                cache[doi] = json.loads(b)["message"]
                time.sleep(0.2)
            c = cache[doi]
            title = (c.get("title") or [""])[0]
            journal = (c.get("container-title") or [""])[0]
            year = None
            for k in ["published-print", "issued", "published-online"]:
                if c.get(k, {}).get("date-parts"):
                    year = str(c[k]["date-parts"][0][0])
                    break
            fam = (c.get("author") or [{}])[0].get("family", "")
            rec["crossref"] = dict(title=title, journal=journal, year=year, volume=c.get("volume"),
                                   issue=c.get("issue"), page=c.get("page") or c.get("article-number"), first_author=fam,
                                   type=c.get("type"), n_authors=len(c.get("author") or []))
            # 標題：文獻字串中應含 Crossref 標題（容許大小寫與標點）
            ts = max(sim(title, ref[i:i + len(title) + 5]) for i in range(0, max(1, len(ref) - len(title)), 3)) if title else 0
            rec["title_sim"] = round(ts, 3)
            if ts < 0.85:
                rec["issues"].append(f"標題不符（相似度 {ts:.2f}）：Crossref＝{title}")
            if fam and norm(fam).split()[0] not in norm(ref[:60]):
                rec["issues"].append(f"第一作者不符：Crossref＝{fam}")
            if year and rec["year_cited"] and year != rec["year_cited"]:
                # 線上早於紙本常差一年，另記
                yrs = {str(c[k]["date-parts"][0][0]) for k in ["published-print", "published-online", "issued"] if c.get(k, {}).get("date-parts")}
                if rec["year_cited"] not in yrs:
                    rec["issues"].append(f"年份不符：引用 {rec['year_cited']}，Crossref {sorted(yrs)}")
            if journal and sim(journal, ref) < 0.2 and norm(journal) not in norm(ref):
                rec["issues"].append(f"期刊名稱請確認：Crossref＝{journal}")
            vol = c.get("volume")
            if vol and not re.search(rf"\b{re.escape(vol)}\b", ref):
                rec["issues"].append(f"卷號不符：Crossref＝{vol}")
            pg = c.get("page")
            if pg:
                first = pg.split("-")[0]
                if first not in ref:
                    rec["issues"].append(f"頁碼不符：Crossref＝{pg}")
            if c.get("relation", {}).get("is-retracted-by") or "retract" in title.lower():
                rec["issues"].append("可能已撤稿")
        except Exception as e:
            rec["issues"].append(f"DOI 查詢失敗：{e}")
    else:
        um = re.search(r"https?://\S+", ref)
        if um:
            url = um.group(0).rstrip(".")
            rec["url"] = url
            try:
                st, b = get(url)
                rec["url_status"] = st
                tm = re.search(rb"<title[^>]*>(.*?)</title>", b, re.S | re.I)
                rec["page_title"] = tm.group(1).decode("utf-8", "ignore").strip()[:200] if tm else None
            except Exception as e:
                rec["issues"].append(f"網址無法開啟：{e}")
        else:
            rec["issues"].append("無 DOI 也無網址（請人工確認來源）")
    out.append(rec)
    print(("OK  " if not rec["issues"] else "CHK ") + ref[:70])


# 內文引用 ↔ 文獻清單
def cites(text):
    res = set()
    for grp in re.findall(r"[（(]([^（）()]*?\d{4}[a-z]?[^（）()]*)[）)]", text):
        for part in re.split(r"[;；]", grp):
            part = part.strip()
            m = re.match(r"(.+?),\s*((?:\d{4}[a-z]?)(?:,\s*\d{4}[a-z]?)*)", part)
            if not m:
                continue
            auth = m.group(1).strip()
            auth = re.sub(r"^(e\.g\.,|例如|見)\s*", "", auth)
            for y in re.findall(r"\d{4}[a-z]?", m.group(2)):
                res.add((auth, y))
    return res


xref = {}
for n, J in docs.items():
    body = "\n".join(i["text"] for i in J["items"] if i["kind"] == "para" and i["text"] not in J["refs"])
    body += "\n" + "\n".join(" ".join(c for row in i["rows"] for c in row) for i in J["items"] if i["kind"] == "table")
    cs = cites(body)
    refs = [r for r in J["refs"] if len(r) >= 30]
    missing, used = [], set()
    for auth, y in sorted(cs):
        key = norm(re.sub(r"\bet al\.?", "", auth)).split()
        key = [k for k in key if k not in ("and", "n", "d")]
        hit = [r for r in refs if key and norm(r[:150]).startswith(key[0]) and re.search(rf"\({y[:4]}{y[4:] or ''}", r)]
        if not hit:
            hit = [r for r in refs if key and key[0] in norm(r[:120]) and re.search(rf"\({y[:4]}", r)]
        if hit:
            used.update(hit)
        else:
            missing.append(f"{auth}, {y}")
    uncited = [r[:90] for r in refs if r not in used]
    xref[n] = dict(n_cites=len(cs), cited_not_listed=missing, listed_not_cited=uncited)

json.dump(dict(refs=out, xref=xref), open("refcheck.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", len(out), "unique refs;", sum(bool(r["issues"]) for r in out), "with issues")
for n, x in xref.items():
    print(n, "cites", x["n_cites"], "missing", len(x["cited_not_listed"]), "uncited", len(x["listed_not_cited"]))
