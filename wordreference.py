#!/usr/bin/env python3
import subprocess as sp
import urllib.request
from bs4 import BeautifulSoup
import re
import sys

# ------------------ Helpers ------------------
def run(cmd):
    return sp.run(cmd, shell=True, stdout=sp.PIPE).stdout.decode().strip()

def notify(title, msg):
    sp.run(["notify-send", "-t", "3000", title, msg])  # Changed from Popen to run

def detect_lang(word):
    try:
        return run(f"trans -b -id '{word}'")
    except Exception:
        return "auto"

# ------------------ Doom One Colors ------------------
COLOR_WORD   = "#61afef"   # blue
COLOR_TYPE   = "#abb2bf"   # gray
COLOR_TRANS  = "#98c379"   # green

# ------------------ Extractors ------------------
def extract_word_and_pos(cell):
    """Extract (word, POS) from WordReference HTML cell."""
    pos = ""
    em = cell.find("em")
    if em:
        pos = em.get_text(strip=True)
    strong = cell.find("strong")
    if strong:
        word = strong.get_text(" ", strip=True)
    else:
        text = cell.get_text(" ", strip=True)
        if pos:
            text = re.sub(r"\(\s*" + re.escape(pos) + r"\s*\)", "", text)
            text = re.sub(r"\b" + re.escape(pos) + r"\b", "", text)
        word = text.strip(" :;")
    return word.strip(), pos.strip()

# ------------------ Main ------------------
word = run("xclip -o -selection primary").strip()
if not word:
    notify("Translator", "⚠ No word selected!")
    sys.exit(0)

src_lang = detect_lang(word)
langs = ["en", "de", "tr", "ar", "fr", "it", "es"]
langs_display = "\n".join(langs)
target_lang = run(f"echo '{langs_display}' | rofi -dmenu -i -p 'Translate {src_lang} →'")
if not target_lang or src_lang == target_lang:
    sys.exit(0)

pair = src_lang + target_lang
url = f"http://www.wordreference.com/{pair}/{word.replace(' ', '+')}"
headers = {"User-Agent": "Mozilla/5.0"}

try:
    req = urllib.request.Request(url, headers=headers)
    page = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(page, "html.parser")

    # --- WordReference Translations ---
    rows = soup.select(f"table.WRD > tr[id^='{pair}']")
    lines = []
    for res in rows:
        fr_cells = res.select("td.FrWrd")
        to_cells = res.select("td.ToWrd")
        for fr, to in zip(fr_cells, to_cells):
            src_word, src_pos = extract_word_and_pos(fr)
            tgt_word, tgt_pos = extract_word_and_pos(to)
            if not src_word or not tgt_word:
                continue
            pos = tgt_pos or src_pos
            line = (
                f"<span color='{COLOR_WORD}'><b>{src_word}</b></span> "
                    + (f"<span color='{COLOR_TYPE}'><i>({pos}) : </i></span> " if pos else "")
                + f"<span color='{COLOR_TRANS}'>{tgt_word}</span>"
            )
            lines.append(line)

    # --- Build Final Output ---
    if not lines:
        raise Exception("No WordReference results")

    output = "\n".join(lines)

    selected = run(
        "rofi -markup-rows -i -dmenu "
        f"-p 'Translation ({src_lang}→{target_lang})' <<< \"{output}\""
    )

    if selected:
        # Copy only translation (last colored span)
        m = re.search(r">([^<]+)</span>\s*$", selected)
        clean = m.group(1).strip() if m else re.sub(r"<[^>]*>", "", selected).strip()
        run(f"printf %s \"{clean}\" | xclip -selection clipboard")
        notify("📋Translation Copied", "")

except Exception:
    translation = run(f"trans -b :{target_lang} '{word}'")
    run(f"printf %s \"{translation}\" | xclip -selection clipboard")
    notify("📋Translation Copied", "")

