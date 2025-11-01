#!/usr/bin/env python3
import subprocess as sp
import urllib.request, urllib.parse, json, os, re, sys, threading
from bs4 import BeautifulSoup

# ---------------- Configuration ----------------
TMP_DIR = "/tmp/translator"
os.makedirs(TMP_DIR, exist_ok=True)
API_KEY = os.getenv("GEMINI_API_KEY", "")
NOTIFY_TIMEOUT = 120000  # 2 min

# Colors (doom-one)
COLOR_WORD = "#61afef"       # blue
COLOR_TYPE = "#abb2bf"       # gray
COLOR_TRANS = "#98c379"      # green
COLOR_EXAMPLES = "#87CEEB"   # light blue

# ---------------- Helpers ----------------
def run(cmd):
    return sp.run(cmd, shell=True, stdout=sp.PIPE).stdout.decode().strip()

def notify(title, msg, timeout=NOTIFY_TIMEOUT):
    sp.run(["notify-send", "-t", str(timeout), title, msg])

def detect_lang(word):
    try:
        return run(f"trans -b -id '{word}'")
    except:
        return "auto"

def call_gemini(prompt):
    """Call Gemini and return text"""
    if not API_KEY:
        return ""
    try:
        payload = json.dumps({"contents":[{"parts":[{"text":prompt}]}]}).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        with open(f"{TMP_DIR}/gemini.log","a") as f: f.write(str(e)+"\n")
        return ""

def play_tts(text, lang):
    if lang.startswith("en"):
        run(f"gtts-cli -l en '{text}' -o {TMP_DIR}/tts.mp3 && mpv --really-quiet {TMP_DIR}/tts.mp3 &")
    elif lang.startswith("de"):
        run(f"espeak-ng -v de '{text}' &")

def extract_word_and_pos(cell):
    pos = ""
    em = cell.find("em")
    if em: pos = em.get_text(strip=True)
    strong = cell.find("strong")
    if strong:
        word = strong.get_text(" ", strip=True)
    else:
        word = cell.get_text(" ", strip=True)
    return word.strip(), pos.strip()

# ---------------- Main ----------------
word = run("xclip -o -selection primary").strip()
if not word:
    notify("Translator", "⚠ No word selected!")
    sys.exit(0)

src_lang = detect_lang(word)
langs = ["en","de","tr","ar","fr","it","es"]
langs_display = "\n".join(langs)
target_lang = run(f"echo '{langs_display}' | rofi -dmenu -i -p 'Translate {src_lang} →'")
if not target_lang:
    sys.exit(0)

# ---------------- Start Gemini in background ----------------
def prepare_gemini():
    translation = run(f"trans -b :{target_lang} '{word}'")
    ipa_src = run(f"espeak-ng -v {src_lang} --ipa -q '{word}'").strip()
    ipa_tgt = run(f"espeak-ng -v {target_lang} --ipa -q '{translation}'").strip()

    # Clean IPA symbols to avoid messy spacing and stress markers
    ipa_src = re.sub(r"[^a-zA-Zɑɐɒæɓʙβɔɕçðɖɗɘəɚɛɜɞɟɠɢɣħɦɧɨɪɫɬɭɮɯɰɱɲɳɴŋɸɹɺɻɽɾʀʁʂʃʄʅʆʇʈʉʊʋʌʍʎʏʐʑʒʔʕʗʘʙʜʝʞʟʡʢʣʤʥʦʧʨʩʪʫʬʭʮʯʰʱʲʳʴʵʶʷʸːˑ˞ˠˡˢˣˤˬˮ˯˰˱˲˳˴˵˶˷˸˹˺˻˼˽˾˿.,/ ]", "", ipa_src)
    ipa_tgt = re.sub(r"[^a-zA-Zɑɐɒæɓʙβɔɕçðɖɗɘəɚɛɜɞɟɠɢɣħɦɧɨɪɫɬɭɮɯɰɱɲɳɴŋɸɹɺɻɽɾʀʁʂʃʄʅʆʇʈʉʊʋʌʍʎʏʐʑʒʔʕʗʘʙʜʝʞʟʡʢʣʤʥʦʧʨʩʪʫʬʭʮʯʰʱʲʳʴʵʶʷʸːˑ˞ˠˡˢˣˤˬˮ˯˰˱˲˳˴˵˶˷˸˹˺˻˼˽˾˿.,/ ]", "", ipa_tgt)

    # Gemini queries
    synonyms = call_gemini(f"Give 5 concise synonyms for '{translation}' in {target_lang}.")
    examples = call_gemini(
        f"Write 3 natural example sentences in {target_lang} using '{translation}', "
        f"and provide their English translations in parentheses (no transliteration, no explanations)."
    )

    # Clean Gemini text
    def clean(text):
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)
        text = re.sub(r"`(.*?)`", r"‘\1’", text)
        text = text.replace("•", "▪")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    synonyms = clean(synonyms)
    examples = clean(examples)

    # Body format (smaller font)
    body = (
        f"<b><span color='#FFD700'>Word:</span></b> <span color='{COLOR_WORD}'>{word}</span>\n"
        f"<b><span color='#FFA500'>Translation:</span></b> <span color='{COLOR_TRANS}'>{translation}</span>\n"
        f"<b><span color='#FF69B4'>IPA:</span></b> /{ipa_src}/ → /{ipa_tgt}/\n\n"
        f"💡 <b>Synonyms:</b>\n{synonyms}\n\n"
        f"🗣️ <b>Examples:</b>\n{examples}"
    )

    notify(f"🌐 Examples ({target_lang})", f"<span font='11'>{body}</span>", timeout=NOTIFY_TIMEOUT)
    if target_lang in ["en","de"]:
        play_tts(translation, target_lang)

threading.Thread(target=prepare_gemini, daemon=True).start()

# ---------------- WordReference lookup (instant) ----------------
pair = src_lang + target_lang
url = f"http://www.wordreference.com/{pair}/{urllib.parse.quote_plus(word)}"
headers = {"User-Agent": "Mozilla/5.0"}

try:
    page = urllib.request.urlopen(urllib.request.Request(url, headers=headers)).read()
    soup = BeautifulSoup(page, "html.parser")
    rows = soup.select(f"table.WRD > tr[id^='{pair}']")
    lines = []
    for r in rows:
        for fr, to in zip(r.select("td.FrWrd"), r.select("td.ToWrd")):
            w1,p1 = extract_word_and_pos(fr)
            w2,p2 = extract_word_and_pos(to)
            if not w1 or not w2: continue
            pos = p2 or p1
            lines.append(f"<b>{w1}</b> ({pos}) → <span color='{COLOR_TRANS}'>{w2}</span>")
    if not lines:
        raise Exception("no wr results")
    out = "\n".join(lines)
    selected = run(f"rofi -markup-rows -i -dmenu -p 'Translation ({src_lang}→{target_lang})' <<< \"{out}\"")
    if selected:
        m = re.search(r">([^<]+)</span>$", selected)
        clean = m.group(1).strip() if m else re.sub(r"<[^>]*>","",selected).strip()
        run(f"printf %s '{clean}' | xclip -selection clipboard")
except Exception:
    trans = run(f"trans -b :{target_lang} '{word}'")
    run(f"printf %s '{trans}' | xclip -selection clipboard")

