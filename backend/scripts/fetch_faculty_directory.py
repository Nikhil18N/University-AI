"""Collect the faculty list again from https://sru.edu.in/faculty/ (run it every few months).

    pip install beautifulsoup4            # once; only this script needs it
    python scripts/fetch_faculty_directory.py data/faculty_raw/sru_faculty_<date>.json
    python scripts/build_faculty_directory.py data/faculty_raw/sru_faculty_<date>.json

Needs internet access to sru.edu.in. It reads the directory page, then each profile page, and
keeps only what the university publishes there (name, role, designation, school, department,
qualification, experience, research areas, interests, subjects, education, work history,
supervision, about). E-mail addresses and phone numbers are not collected.

The page structure this expects (checked 17 Nov 2026): directory cards ".faculty-card" under
school headings; profiles with ".profile-header", "#about" (with ".about-faculty-right-meta"),
"#education", "#experience" and "#subjects". If the website is redesigned, adjust parse_* below.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone

import httpx

DIRECTORY = "https://sru.edu.in/faculty/"
FIELDS = ["name", "role", "designation", "school", "department", "qualification", "experience_years",
          "research", "research_areas", "interests", "subjects", "education", "work", "supervision", "about", "url"]


def _clean(text) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_directory(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out, school = [], None
    for node in soup.select("h2, h3, h4, .faculty-card"):
        classes = node.get("class") or []
        if "faculty-card" not in classes:
            text = _clean(node.get_text())
            if re.search(r"School|Astra|Institute|Centre|Department", text) and not re.match(r"(Head|Dean)\b", text):
                school = text
            continue
        link = node.select_one('a[href*="/faculty/"]')
        name = _clean((node.select_one("h5") or node).get_text())
        lines = [_clean(x) for x in node.get_text("\n").split("\n") if _clean(x)]
        research = lines[lines.index("Research Area") + 1:] if "Research Area" in lines else []
        designation = lines[lines.index(name) + 1] if name in lines and lines.index(name) + 1 < len(lines) else ""
        out.append({"school": school, "name": name, "designation": designation,
                    "research": "; ".join(research), "url": link["href"] if link else None})
    return [r for r in out if r["url"]]


def _items(el) -> list[str]:
    leaves = [_clean(x.get_text()) for x in el.select("li, p, span") if not x.select("li, p")]
    leaves = [x for x in leaves if x]
    return leaves or [_clean(el.get_text())]


def parse_profile(html: str, name: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("a[href^='mailto:'], a[href^='tel:']"):
        tag.decompose()  # never collect contact details
    header = soup.select_one(".profile-header")
    ht = _clean(header.get_text(" ")) if header else ""
    deps = re.findall(r"Department of ([A-Za-z&,. ]+?)(?= Ph\.D| PhD| M\.| B\.| MBA| MSc| Years| Highest| •|$)", ht)
    qual = re.search(r"((?:Ph\.?D\.?|PhD|M\.?\s?Tech|M\.?E\.?|M\.?Sc|MBA|M\.?Com|M\.?A\.|M\.?Phil|D\.Sc)[^•]*?) "
                     r"Years of Experience", ht)
    exp = re.search(r"Years of Experience (\d+)", ht)
    role = _clean(ht.split(name)[0].replace("Ph.D", "", 1)) if name and name in ht else ""
    about, meta = soup.select_one("#about"), {}
    about_text = ""
    if about:
        right = about.select_one(".about-faculty-right-meta")
        if right:
            for h5 in right.select("h5"):
                vals, sib = [], h5.find_next_sibling()
                while sib is not None and sib.name != "h5":
                    vals += _items(sib)
                    sib = sib.find_next_sibling()
                meta[_clean(h5.get_text())] = "; ".join(dict.fromkeys(vals))
            right.decompose()
        about_text = _clean(about.get_text(" "))

    def tab(tab_id):
        el = soup.select_one(f"#{tab_id}")
        if not el:
            return ""
        rows = [_clean(x.get_text(" ")) for x in el.select("li, .row, tr") if not x.select("li, .row, tr")]
        rows = [r for r in rows if r]
        return "; ".join(dict.fromkeys(rows)) if rows else _clean(el.get_text(" "))

    return {"department": deps[-1].strip() if deps else "", "qualification": _clean(qual.group(1)) if qual else "",
            "experience_years": exp.group(1) if exp else "", "role": role,
            "about": about_text[:700], "research_areas": meta.get("Research Areas", "")[:400],
            "interests": meta.get("Interests", "")[:300], "supervision": meta.get("Student Supervision", "")[:150],
            "education": tab("education")[:350], "work": tab("experience")[:350],
            "subjects": re.sub(r"→\s*•?\s*", "", tab("subjects"))[:250]}


def main(out_path: str):
    headers = {"User-Agent": "SRU-Buddy-faculty-refresh/1.0 (admissions assistant)"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        cards = parse_directory(client.get(DIRECTORY).text)
        seen, rows = set(), []
        for i, card in enumerate(cards, 1):
            if card["url"] in seen:
                continue
            seen.add(card["url"])
            try:
                card.update(parse_profile(client.get(card["url"]).text, card["name"]))
            except Exception as exc:  # keep the directory entry even if one profile fails
                print(f"  could not read {card['url']}: {exc}")
            rows.append([card.get(f, "") or "" for f in FIELDS])
            if i % 25 == 0:
                print(f"  {i}/{len(cards)} profiles")
            time.sleep(0.2)  # be gentle with the university website
    payload = {"source": DIRECTORY, "collected_at": datetime.now(timezone.utc).isoformat(), "fields": FIELDS,
               "rows": rows}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print(f"{len(rows)} faculty saved to {out_path}. Next: python scripts/build_faculty_directory.py {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
