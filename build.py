#!/usr/bin/env python3
"""Build one page per venue.

  cafes/<slug>.json        ->  dist/cafe/<slug>/index.html        (link: /cafe/<slug>/)
  restaurants/<slug>.json  ->  dist/restaurant/<slug>/index.html  (link: /restaurant/<slug>/)

Run from the repo root:  python build.py
Images (logo, banner) go in a folder with the same name next to the json,
e.g. cafes/<slug>/logo.jpg, and are copied next to the built page.
"""
import csv, html, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template" / "cafe-template.html"
DIST = ROOT / "dist"
KINDS = {"cafe": ROOT / "cafes", "restaurant": ROOT / "restaurants"}
RESERVED = {"index", "assets"}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
BLOCK = re.compile(r"/\*CAFE_START\*/.*?/\*CAFE_END\*/", re.S)


def load_csv(path):
    """menu.csv columns: category, item, price, note (note is optional)."""
    cats, order = {}, []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for n, raw in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            cat, item, note = row.get("category", ""), row.get("item", ""), row.get("note", "")
            price = row.get("price", "").replace("\u20b9", "").replace(",", "")
            if not (cat or item or price):
                continue
            if not cat or not item:
                raise ValueError(f"row {n}: category and item are required")
            try:
                p = float(price)
            except ValueError:
                raise ValueError(f"row {n}: price {price!r} is not a number")
            p = int(p) if p == int(p) else p
            if cat not in cats:
                cats[cat] = []
                order.append(cat)
            cats[cat].append([item, p] + ([note] if note else []))
    return [{"cat": k, "items": cats[k]} for k in order]


def check(src, slug, c):
    errs = []
    if not SLUG.match(slug) or slug in RESERVED:
        errs.append("file name must be lowercase letters, numbers and dashes, e.g. blue-tokai.json")
    for k in ("name", "tagline", "accent", "review", "instagram"):
        if not c.get(k):
            errs.append(f"missing '{k}'")
    if c.get("accent") and not HEX.match(c["accent"]):
        errs.append("'accent' must be a 6-digit hex color like #2F5D50")
    if not (c.get("menu") or c.get("menuPdf") or c.get("menuImages")):
        errs.append("add a menu: a menu.csv file, 'menu', 'menuImages' or a 'menuPdf' link")
    for img in c.get("menuImages") or []:
        if not (src / slug / img).is_file():
            errs.append(f"menu image not found: {src.name}/{slug}/{img}")
    wifi = c.get("wifi")
    if wifi is not None and not (wifi.get("name") and wifi.get("password")):
        errs.append("'wifi' needs a name and password, or set it to null")
    for cat in c.get("menu") or []:
        if not cat.get("cat") or not cat.get("items"):
            errs.append(f"menu category needs 'cat' and 'items': {cat.get('cat')!r}")
            continue
        for it in cat["items"]:
            if not (isinstance(it, list) and 2 <= len(it) <= 3 and isinstance(it[1], (int, float))):
                errs.append(f"bad item in '{cat['cat']}': {it!r} (use [name, price] or [name, price, note])")
    for k in ("logo", "banner"):
        f = c.get(k)
        if f and not (src / slug / f).is_file():
            errs.append(f"'{k}' file not found: {src.name}/{slug}/{f}")
    return errs


def main():
    template = TEMPLATE.read_text(encoding="utf-8")
    if not BLOCK.search(template):
        sys.exit("template is missing the CAFE_START / CAFE_END markers")
    jobs, failed = [], False
    for kind, src in KINDS.items():
        for path in sorted(src.glob("*.json")) if src.is_dir() else []:
            slug = path.stem
            label = f"{src.name}/{path.name}"
            try:
                c = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"[x] {label}: invalid JSON ({e})")
                failed = True
                continue
            csv_path = src / slug / "menu.csv"
            if not c.get("menu") and csv_path.is_file():
                try:
                    c["menu"] = load_csv(csv_path)
                except ValueError as e:
                    print(f"[x] {src.name}/{slug}/menu.csv: {e}")
                    failed = True
                    continue
            errs = check(src, slug, c)
            for e in errs:
                print(f"[x] {label}: {e}")
            failed = failed or bool(errs)
            jobs.append((kind, src, slug, c))
    if failed:
        sys.exit("Fix the errors above. Nothing was built.")
    for kind, src, slug, c in jobs:
        data = json.dumps(c, ensure_ascii=False, indent=2).replace("</", "<\\/")
        page = BLOCK.sub(lambda m: "/*CAFE_START*/" + data + "/*CAFE_END*/", template, count=1)
        page = page.replace("<title>Cafe</title>", f"<title>{html.escape(c['name'])}</title>", 1)
        out = DIST / kind / slug
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        (out / "index.html").write_text(page, encoding="utf-8")
        assets = src / slug
        if assets.is_dir():
            for f in assets.iterdir():
                if f.is_file() and f.suffix.lower() != ".csv":
                    shutil.copy2(f, out / f.name)
        print(f"[ok] /{kind}/{slug}/")
    print(f"Built {len(jobs)} page(s).")

if __name__ == "__main__":
    main()
