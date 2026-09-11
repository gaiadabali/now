import json

def load_jsonl(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

wxr = load_jsonl('bali/content/extracted/articles.jsonl')
rest = load_jsonl('bali/content/harvested/articles.jsonl')

print("WXR extracted total rows:", len(wxr))
print("REST harvested total rows:", len(rest))

# published count
def status_of(a):
    return a.get('status')

wxr_pub = [a for a in wxr if status_of(a) == 'publish' or status_of(a) == 'published']
rest_pub = [a for a in rest if status_of(a) == 'publish' or status_of(a) == 'published']
print("WXR published:", len(wxr_pub))
print("REST published:", len(rest_pub))
print("WXR status value set:", set(status_of(a) for a in wxr))
print("REST status value set:", set(status_of(a) for a in rest))

attachments = load_jsonl('bali/content/extracted/attachments.jsonl')
print("attachments count:", len(attachments))

# Yoast focus keywords on published articles
def yoast_count(articles):
    n = 0
    for a in articles:
        meta = a.get('meta', {})
        fk = meta.get('_yoast_wpseo_focuskw')
        if fk:
            n += 1
    return n

print("WXR published yoast focuskw:", yoast_count(wxr_pub))
print("WXR all yoast focuskw:", yoast_count(wxr))

geo = load_jsonl('bali/content/extracted/geo.jsonl')
print("geo.jsonl rows:", len(geo))
