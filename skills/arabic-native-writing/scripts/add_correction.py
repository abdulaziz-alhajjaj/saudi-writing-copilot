#!/usr/bin/env python3
"""يسجّل تصحيحًا شخصيًّا ليلتقطه الفاحص في الجلسات التالية.

الاستعمال:
    python3 add_correction.py --wrong "يضرب على الوتر الصحيح" \\
        --fix "يصيب موضع الحاجة" --why "استعارة منقولة من strike a chord"
    python3 add_correction.py --list
    python3 add_correction.py --export          # صفوف جاهزة لمشاركتها في Issue أو PR

يُحفظ في ~/.arabic-native-writing/corrections.csv (أو المسار في ARABIC_NATIVE_CORRECTIONS)،
خارج مجلد المهارة. كل صف يُوسَم «غير مراجَع» حتى يؤكده متحدث.
يلتقط الفاحص العبارة نفسها (بتنوّع التشكيل والهمزات)، لا تصريفاتها ولا الأنماط المشابهة لها.
لتغطية التصريف مرِّر --regex بنمط مثل «[يتنا]ضرب\\s+(?:على\\s+)?الوتر».
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calque_check import USER_CSV, norm_full  # noqa: E402

COLS = ["id", "category", "severity", "norm", "english_source", "calque_ar", "regex",
        "why_wrong", "fix_fusha_white", "fix_najdi_white", "confidence"]
STRIP = re.compile(r"[«»\"'“”.,،؛;:؟?!…()\[\]]")


def phrase_to_regex(phrase):
    words = [w for w in STRIP.sub(" ", norm_full(phrase)).split() if w]
    if not words:
        raise ValueError("العبارة فارغة")
    body = r"\s+".join(re.escape(w) for w in words)
    return rf"(?<![ء-ي]){body}(?![ء-ي])"


def read_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="تسجيل تصحيح شخصي للفاحص")
    ap.add_argument("--wrong", help="العبارة الخاطئة كما وردت")
    ap.add_argument("--fix", help="الصياغة الصحيحة (فصحى بيضاء)")
    ap.add_argument("--fix-najdi", default="", help="الصياغة المحكية إن لزمت")
    ap.add_argument("--why", default="", help="سبب الخطأ بجملة")
    ap.add_argument("--source", default="", help="الأصل الإنجليزي إن عُرف")
    ap.add_argument("--severity", default="error", choices=["error", "check", "style"])
    ap.add_argument("--regex", help="نمط جاهز بدل المولَّد من العبارة (مثلًا لتغطية تصريفات الفعل: [يت]ضرب)؛ يُكتب على النص المطبَّع بلا تشكيل ولا همزات")
    ap.add_argument("--list", action="store_true", help="اعرض التصحيحات المسجَّلة")
    ap.add_argument("--export", action="store_true", help="اطبع صفوفًا للمشاركة (بلا معرّفات شخصية)")
    a = ap.parse_args()

    rows = read_rows(USER_CSV)
    if a.list or a.export:
        for r in rows:
            if a.export:
                print(f'{r["calque_ar"]} ← {r["fix_fusha_white"]} | {r["why_wrong"]}')
            else:
                print(f'{r["id"]} [{r["severity"]}] {r["calque_ar"]} ← {r["fix_fusha_white"]}')
        if not rows:
            print("لا تصحيحات مسجَّلة.")
        return
    if not a.wrong or not a.fix:
        ap.error("--wrong و --fix مطلوبان")

    if a.regex:
        rx = norm_full(a.regex)
        try:
            re.compile(rx)
        except re.error as e:
            ap.error(f"النمط غير صالح: {e}")
    else:
        rx = phrase_to_regex(a.wrong)
    for r in rows:
        if r["regex"] == rx:
            print(f'مسجَّل من قبل: {r["id"]} {r["calque_ar"]}')
            return
    nums = [int(m.group(1)) for r in rows if (m := re.match(r"U(\d+)$", r["id"]))]
    rid = f"U{(max(nums) + 1 if nums else 1):03d}"
    row = {
        "id": rid, "category": "تصحيح شخصي", "severity": a.severity, "norm": "full",
        "english_source": a.source, "calque_ar": f"«{a.wrong.strip()}»", "regex": rx,
        "why_wrong": a.why or "صحّحه المستخدم", "fix_fusha_white": a.fix,
        "fix_najdi_white": a.fix_najdi, "confidence": "غير مراجَع",
    }
    os.makedirs(os.path.dirname(USER_CSV), exist_ok=True)
    new = not os.path.isfile(USER_CSV)
    with open(USER_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_ALL)
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"سُجِّل {rid}: «{a.wrong.strip()}» ← «{a.fix}» ({USER_CSV})")


if __name__ == "__main__":
    main()
