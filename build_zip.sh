#!/usr/bin/env bash
# يبني arabic-native-writing.zip لرفعه في تطبيق Claude. شغّله بعد أي تعديل على المهارة.
set -e
cd "$(dirname "$0")"
find arabic-native-writing -name __pycache__ -prune -exec rm -rf {} +
rm -f arabic-native-writing.zip
zip -rq arabic-native-writing.zip arabic-native-writing
echo "تم: arabic-native-writing.zip"
