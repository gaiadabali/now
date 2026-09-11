import json

def load(path):
    d = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            d[obj['wp_id']] = obj
    return d

a_dump = load('jakarta/content/extracted/attachments.jsonl')
a_wxr = load('jakarta/content/extracted-wxr/attachments.jsonl')
print("attachments dump:", len(a_dump), "wxr:", len(a_wxr))
print("unique to dump:", len(set(a_dump) - set(a_wxr)))
print("unique to wxr:", len(set(a_wxr) - set(a_dump)))

art_dump = load('jakarta/content/extracted/articles.jsonl')
art_wxr = load('jakarta/content/extracted-wxr/articles.jsonl')

def yoast_count(articles):
    n = 0
    for a in articles.values():
        meta = a.get('meta', {})
        fk = meta.get('_yoast_wpseo_focuskw')
        if fk:
            n += 1
    return n

print("dump yoast focuskw count:", yoast_count(art_dump))
print("wxr yoast focuskw count:", yoast_count(art_wxr))

# also check possible alternate key names
sample_meta_keys = set()
for a in list(art_dump.values())[:50]:
    sample_meta_keys |= set(a.get('meta', {}).keys())
print("sample meta keys (dump):", [k for k in sample_meta_keys if 'yoast' in k.lower() or 'focus' in k.lower()])
