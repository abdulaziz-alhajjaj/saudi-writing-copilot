#!/usr/bin/env bash
# يبني arabic-native-writing.zip لرفعه في تطبيق Claude (المجلد في جذر الملف). شغّله بعد أي تعديل على المهارة.
set -e
cd "$(dirname "$0")"
find skills/arabic-native-writing -name __pycache__ -prune -exec rm -rf {} +
rm -f arabic-native-writing.zip
(cd skills && zip -rq ../arabic-native-writing.zip arabic-native-writing)
echo "تم: arabic-native-writing.zip"
