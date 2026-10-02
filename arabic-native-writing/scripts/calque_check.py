#!/usr/bin/env python3
"""فاحص الكاليكات والإيقاع للنص العربي.

الاستعمال:
    python3 calque_check.py نص.txt
    cat نص.txt | python3 calque_check.py -
    python3 calque_check.py نص.txt --json
    python3 calque_check.py نص.txt --csv مسار/آخر.csv

يكشف الأنماط المعروفة في references/07-calques.csv، ويفحص الإيقاع والترقيم
والمكرَّرات. أداة مساعدة: لا تغني عن القراءة البشرية، وقد تُخطئ في الاتجاهين.
الأرقام العتبية (مثل حدّ الجمل القصيرة) تقديرات عملية وليست مقاسة.
"""
import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "..", "references", "07-calques.csv")
# تصحيحات المستخدم الشخصية: خارج مجلد المهارة حتى لا تضيع بتحديثها. يُغيَّر المسار بالمتغير ARABIC_NATIVE_CORRECTIONS
USER_CSV = os.environ.get(
    "ARABIC_NATIVE_CORRECTIONS",
    os.path.join(os.path.expanduser("~"), ".arabic-native-writing", "corrections.csv"),
)

DIACRITICS = re.compile(r"[ً-ٰٟـ]")
SENT_SPLIT = re.compile(r"(?<=[.!?؟…])\s+|\n+")
WORD = re.compile(r"[ء-ي٠-٩A-Za-z0-9]+")
ARABIC_LETTER = re.compile(r"[ء-ي]")

SHORT_WORDS = 6      # جملة "قصيرة" إن لم تزد على هذا العدد
SHORT_RUN = 3        # عدد القصيرات المتتالية الذي ينبّه
LONG_SENT = 60       # جملة تُعدّ طويلة جدًّا
NEG_PAR_MAX_SHORT = 1   # «لا/ليس … بل/وإنما» في نص أقل من 250 كلمة
NEG_PAR_MAX_LONG = 2    # في نص أطول (تقدير عملي، انظر 09-method-and-limits)
CONNECTOR_LIMITS = {  # لكل 1000 كلمة (تقديرات عملية)
    "من خلال": 4,
    "حيث": 4,
    "كما أن": 3,
    "بالإضافة إلى ذلك": 1,
    "هذا يعني أن": 2,
}


def norm_full(s):
    s = DIACRITICS.sub("", s)
    return (
        s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ٱ", "ا").replace("ى", "ي")
    )


def norm_diac(s):
    return DIACRITICS.sub("", s)


def normalize_with_map(text, mode):
    """يعيد النص المطبَّع وخريطة من موضع المطبَّع إلى موضع الأصل."""
    out, idx = [], []
    for i, ch in enumerate(text):
        if DIACRITICS.match(ch):
            continue
        if mode == "full":
            ch = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"}.get(ch, ch)
        out.append(ch)
        idx.append(i)
    return "".join(out), idx


def load_rules(path):
    rules = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rx = (row.get("regex") or "").strip()
            if not rx:
                continue
            mode = (row.get("norm") or "full").strip() or "full"
            pat = norm_full(rx) if mode == "full" else norm_diac(rx)
            try:
                row["_rx"] = re.compile(pat, re.MULTILINE)
            except re.error as e:
                print(f"تحذير: خطأ في regex {row.get('id')}: {e}", file=sys.stderr)
                continue
            row["_mode"] = mode
            rules.append(row)
    return rules


LIST_LINE = re.compile(r"^\s*(?:[-*•|#>]|\d+[.)])")


def split_sentences(text):
    # بنود القوائم والجداول والعناوين ليست جملًا؛ تُستبعد من فحص الإيقاع
    text = "\n".join(l for l in text.split("\n") if not LIST_LINE.match(l))
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p and p.strip()]
    return parts


def count_words(s):
    return len(WORD.findall(s))


def first_words(s, n=6):
    return " ".join(s.split()[:n])


def check(text, rules):
    findings = []

    # أ) الأنماط المعروفة
    caches = {}
    for r in rules:
        mode = r["_mode"]
        if mode not in caches:
            caches[mode] = normalize_with_map(text, mode)
        norm_text, idx = caches[mode]
        for m in r["_rx"].finditer(norm_text):
            if m.end() == m.start():
                continue
            s = idx[m.start()]
            e = idx[m.end() - 1] + 1
            findings.append({
                "kind": "calque",
                "id": r["id"],
                "severity": r["severity"],
                "match": text[s:e].strip(),
                "why": r["why_wrong"],
                "fix": r["fix_fusha_white"],
            })

    sents = split_sentences(text)
    wc = [count_words(s) for s in sents]
    total_words = sum(wc)

    # ب) الإيقاع المبتور
    run, run_start = 0, None
    for i, n in enumerate(wc):
        if 0 < n <= SHORT_WORDS:
            if run == 0:
                run_start = i
            run += 1
        else:
            if run >= SHORT_RUN:
                findings.append({
                    "kind": "rhythm", "severity": "error", "id": "N02",
                    "match": " | ".join(sents[run_start:run_start + run]),
                    "why": f"{run} جمل قصيرة متتالية (إيقاع مبتور).",
                    "fix": "اربطها في جملة أو جملتين بأدوات ربط، واترك قصيرة واحدة للارتكاز.",
                })
            run, run_start = 0, None
    if run >= SHORT_RUN:
        findings.append({
            "kind": "rhythm", "severity": "error", "id": "N02",
            "match": " | ".join(sents[run_start:run_start + run]),
            "why": f"{run} جمل قصيرة متتالية (إيقاع مبتور).",
            "fix": "اربطها في جملة أو جملتين بأدوات ربط، واترك قصيرة واحدة للارتكاز.",
        })

    short_count = sum(1 for n in wc if 0 < n <= SHORT_WORDS)
    if len(sents) >= 4 and short_count / len(sents) >= 0.5:
        findings.append({
            "kind": "rhythm", "severity": "error", "id": "N02",
            "match": f"{short_count} من {len(sents)} جمل قصيرة",
            "why": "أغلب الجمل قصيرة (إيقاع مبتور).",
            "fix": "اربط الجمل بأدوات ربط، واترك قصيرة واحدة للارتكاز بعد جملة طويلة.",
        })

    for s, n in zip(sents, wc):
        if n > LONG_SENT:
            findings.append({
                "kind": "length", "severity": "style", "id": "L01",
                "match": first_words(s, 8) + " …",
                "why": f"جملة من {n} كلمة.",
                "fix": "قسّمها عند أداة الربط الأقرب.",
            })

    # ج) تكرار افتتاح الجمل
    if len(sents) >= 5:
        starts = {}
        for s in sents:
            w = s.split()[0] if s.split() else ""
            starts[w] = starts.get(w, 0) + 1
        for w, c in starts.items():
            if c >= max(4, int(0.3 * len(sents))):
                findings.append({
                    "kind": "openers", "severity": "style", "id": "O01",
                    "match": w,
                    "why": f"{c} جمل من {len(sents)} تبدأ بالكلمة نفسها.",
                    "fix": "نوّع الافتتاح (ظرف، استفهام، شرط، مفعول مقدّم).",
                })

    # د) مكرَّرات
    if total_words >= 80:
        for phrase, limit in CONNECTOR_LIMITS.items():
            c = len(re.findall(re.escape(norm_full(phrase)), norm_full(text)))
            per_k = c * 1000.0 / total_words
            if per_k > limit and c >= 2:
                findings.append({
                    "kind": "overuse", "severity": "style", "id": "V01",
                    "match": phrase,
                    "why": f"تكرر {c} مرة (≈{per_k:.1f} لكل ألف كلمة).",
                    "fix": "نوّع الأداة (انظر جدول الربط في 02-constructions).",
                })

    # د2) النفي المتوازي «ليس/لا … بل/وإنما» (علامة شائعة على النص الآلي)
    ntext = norm_full(text)
    neg = re.findall(
        r"(?<![ء-ي])[وف]?(?:لا|لم|ليس\w*|ما\s+هو)(?![ء-ي])[^.؟!\n]{2,90}?(?<![ء-ي])(?:بل|وانما|انما)(?![ء-ي])",
        ntext)
    limit = NEG_PAR_MAX_SHORT if total_words < 250 else NEG_PAR_MAX_LONG
    if len(neg) > limit:
        findings.append({
            "kind": "neg_parallel", "severity": "style", "id": "N07",
            "match": f"{len(neg)} مرات",
            "why": "تكرار «لا/ليس … بل/وإنما» (يُوصف بأنه علامة على الكتابة الآلية).",
            "fix": "أبقِ واحدة، وبدّل الباقي بـ«غير أنّ» أو «أمّا … فـ» أو جملة إيجابية صريحة.",
        })

    # هـ) كلمات لاتينية خارج القوسين
    outside = re.sub(r"\([^)]*\)", "", text)
    latin = re.findall(r"[A-Za-z]{3,}", outside)
    if len(latin) > 2:
        findings.append({
            "kind": "latin", "severity": "check", "id": "F01",
            "match": ", ".join(latin[:5]),
            "why": f"{len(latin)} كلمة لاتينية خارج الأقواس.",
            "fix": "اكتب المصطلح بالعربية، واجعل الأجنبي بين قوسين عند أول ورود فقط.",
        })

    stats = {
        "sentences": len(sents),
        "words": total_words,
        "mean_sentence_words": round(total_words / len(sents), 1) if sents else 0,
        "short_sentences": sum(1 for n in wc if 0 < n <= SHORT_WORDS),
    }
    return findings, stats


def render(findings, stats):
    order = {"error": 0, "check": 1, "style": 2}
    findings = sorted(findings, key=lambda f: order.get(f["severity"], 3))
    lines = [
        f"الجمل: {stats['sentences']} | الكلمات: {stats['words']} | "
        f"متوسط الجملة: {stats['mean_sentence_words']} كلمة | "
        f"الجمل القصيرة (≤{SHORT_WORDS}): {stats['short_sentences']}"
    ]
    if not findings:
        lines.append("لا ملاحظات من الأنماط المعروفة. (القراءة البشرية تبقى لازمة.)")
        return "\n".join(lines)
    label = {"error": "خطأ", "check": "تحقق", "style": "أسلوب"}
    for f in findings:
        lines.append(
            f"[{label.get(f['severity'], f['severity'])}] {f['id']} «{f['match']}» — "
            f"{f['why']} ← {f['fix']}"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="فاحص الكاليكات والإيقاع للنص العربي")
    ap.add_argument("path", help="ملف نصي، أو - للقراءة من الإدخال القياسي")
    ap.add_argument("--csv", default=DEFAULT_CSV, help="جدول الكاليكات")
    ap.add_argument("--json", action="store_true", help="مخرجات JSON")
    ap.add_argument("--no-user", action="store_true", help="تجاهل ملف تصحيحات المستخدم")
    ap.add_argument("--strict", action="store_true",
                    help="رمز خروج 2 (والتقرير على stderr) إن وُجدت ملاحظة بدرجة «خطأ»؛ للربط بخطّاف أو سكربت")
    args = ap.parse_args()

    text = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    rules = load_rules(args.csv)
    if not args.no_user and os.path.isfile(USER_CSV):
        try:
            rules += load_rules(USER_CSV)
        except Exception as e:  # ملف تالف لا يوقف الفحص
            print(f"تحذير: تعذّرت قراءة تصحيحات المستخدم ({USER_CSV}): {e}", file=sys.stderr)
    findings, stats = check(text, rules)
    if args.json:
        print(json.dumps({"stats": stats, "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(render(findings, stats))
    if args.strict and any(f.get("severity") == "error" for f in findings):
        sys.stderr.write("أخطاء كاليك: أعد صياغة المواضع المذكورة ثم أعد الفحص.\n" + render(findings, stats) + "\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
