import sys, codecs
try:
    with codecs.open('backend.log', 'r', encoding='utf-16le') as f:
        print(f.read())
except Exception:
    with codecs.open('backend.log', 'r', encoding='utf-8') as f:
        print(f.read())
