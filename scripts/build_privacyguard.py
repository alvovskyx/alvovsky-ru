#!/usr/bin/env python3
"""Сборка privacyguard/index.html из src/privacyguard.html и privacyguard/public.json.

Использование: python3 scripts/build_privacyguard.py [путь/к/public.json]
Если путь передан, файл сначала копируется в privacyguard/public.json.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "privacyguard.html"
DATA = ROOT / "privacyguard" / "public.json"
OUT = ROOT / "privacyguard" / "index.html"

TOKEN_RE = re.compile(r"\{\{([A-Za-z0-9_.]+)((?:\|[^|{}]+)*)\}\}")


def plural(n, f1, f2, f3):
    """Русская форма слова для числа: 1 день, 2 дня, 5 дней; 11-14 -> f3."""
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return f3
    n %= 10
    if n == 1:
        return f1
    if 2 <= n <= 4:
        return f2
    return f3


def ru_date(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def build_context(data):
    ctx = {}
    for k, v in data.get("metrics", {}).items():
        ctx[f"metrics.{k}"] = v
    for k, v in data.get("base", {}).items():
        ctx[f"base.{k}"] = v
    for row in data.get("by_type", []):
        if row.get("type") == "Работодатели":
            for k, v in row.items():
                if k != "type":
                    ctx[f"emp.{k}"] = v
    m = data["metrics"]
    ctx["x.open"] = m["in_progress"] + m["waiting"]
    ctx["x.refused_all"] = m["disputed"] + m["refused"]
    ctx["started_ru"] = ru_date(data["started"])
    ctx["generated_ru"] = ru_date(data["generated"])
    return ctx


def substitute(html, ctx):
    def repl(match):
        key, filters = match.group(1), match.group(2)
        if key not in ctx:
            raise SystemExit(f"Неизвестный токен: {key}")
        val = ctx[key]
        if filters:
            forms = filters[1:].split("|")
            if len(forms) != 3:
                raise SystemExit(f"Токен {key}: нужно 3 формы слова")
            return plural(val, *forms)
        return str(val)

    out = TOKEN_RE.sub(repl, html)
    if "{{" in out:
        raise SystemExit("В шаблоне остались нераскрытые токены {{")
    return out


PREP_RE = re.compile(
    r"(?<![\w&;#])(в|с|к|о|у|и|а|на|по|до|из|от|не|за|В|С|К|О|У|И|А|На|По|До|Из|От|Не|За) ")


def typo_text(text):
    # неразрывный пробел после коротких предлогов, союзов и частиц
    text = PREP_RE.sub(lambda m: m.group(1) + "&nbsp;", text)
    # неразрывный пробел перед последним словом текстового узла
    stripped = text.rstrip()
    if stripped and re.search(r"[A-Za-zА-Яа-яЁё0-9».)]$", stripped):
        m = re.search(r" ([^\s]+)$", stripped)
        if m and len(m.group(1)) > 1:
            stripped = stripped[: m.start()] + "&nbsp;" + m.group(1)
            text = stripped + text[len(text.rstrip()):]
    return text


TAG_RE = re.compile(r"(<[^>]+>)", re.S)


def typo(html):
    """Типографика только для текстовых узлов (не атрибуты, не script/style)."""
    parts = TAG_RE.split(html)
    out = []
    skip = 0
    for part in parts:
        low = part.lower()
        if part.startswith("<"):
            if re.match(r"<\s*(script|style)[\s>]", low):
                skip += 1
            elif re.match(r"<\s*/\s*(script|style)\s*>", low):
                skip = max(0, skip - 1)
            out.append(part)
        elif part and skip == 0:
            out.append(typo_text(part))
        else:
            out.append(part)
    return "".join(out)


def main():
    if len(sys.argv) > 1:
        shutil.copyfile(sys.argv[1], DATA)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    ctx = build_context(data)
    html = SRC.read_text(encoding="utf-8")
    for dash in ("—", "–"):
        if dash in html:
            raise SystemExit(f"В шаблоне найдено тире {dash!r}")
    html = substitute(html, ctx)
    html = typo(html)
    OUT.write_text(html, encoding="utf-8")
    print(f"OK: {OUT}")


if __name__ == "__main__":
    main()


# Проверки функции склонения
assert plural(1, "день", "дня", "дней") == "день"
assert plural(2, "день", "дня", "дней") == "дня"
assert plural(5, "день", "дня", "дней") == "дней"
assert plural(11, "день", "дня", "дней") == "дней"
assert plural(21, "день", "дня", "дней") == "день"
assert plural(22, "день", "дня", "дней") == "дня"
assert plural(15, "день", "дня", "дней") == "дней"
