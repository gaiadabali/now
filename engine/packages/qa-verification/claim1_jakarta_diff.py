import json, sys

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

dump = load('jakarta/content/extracted/articles.jsonl')
wxr = load('jakarta/content/extracted-wxr/articles.jsonl')

dump_ids = set(dump.keys())
wxr_ids = set(wxr.keys())

print(f"dump articles: {len(dump_ids)}")
print(f"wxr articles: {len(wxr_ids)}")
print(f"unique to dump: {len(dump_ids - wxr_ids)}")
print(f"unique to wxr: {len(wxr_ids - dump_ids)}")
if dump_ids - wxr_ids:
    print("  dump-only sample:", list(dump_ids - wxr_ids)[:10])
if wxr_ids - dump_ids:
    print("  wxr-only sample:", list(wxr_ids - dump_ids)[:10])

common = dump_ids & wxr_ids
print(f"common: {len(common)}")

# Now check content_html field: does dump.replace('\r\n','\n') == wxr for ALL differing rows?
content_diff_ids = []
crlf_explains_all = True
non_crlf_examples = []
for wid in common:
    dh = dump[wid].get('content_html', '')
    wh = wxr[wid].get('content_html', '')
    if dh != wh:
        content_diff_ids.append(wid)
        if dh.replace('\r\n', '\n') != wh:
            crlf_explains_all = False
            non_crlf_examples.append(wid)

print(f"\ncontent_html differing rows: {len(content_diff_ids)}")
print(f"CRLF hypothesis explains ALL: {crlf_explains_all}")
print(f"rows where CRLF hypothesis FAILS: {len(non_crlf_examples)}")
if non_crlf_examples:
    print("  examples:", non_crlf_examples[:20])

# meta diffs
meta_diff_ids = []
meta_diff_keys_all = set()
non_wpb_examples = []
for wid in common:
    dm = dump[wid].get('meta', {})
    wm = wxr[wid].get('meta', {})
    if dm != wm:
        meta_diff_ids.append(wid)
        # find which keys differ
        all_keys = set(dm.keys()) | set(wm.keys())
        diffkeys = {k for k in all_keys if dm.get(k) != wm.get(k)}
        meta_diff_keys_all |= diffkeys
        if diffkeys != {'wpb_post_views_count'}:
            non_wpb_examples.append((wid, diffkeys))

print(f"\nmeta differing rows: {len(meta_diff_ids)}")
print(f"all differing meta keys seen across all rows: {meta_diff_keys_all}")
print(f"rows whose diff-key-set != {{'wpb_post_views_count'}}: {len(non_wpb_examples)}")
if non_wpb_examples:
    print("  examples:", non_wpb_examples[:20])

# categories diffs
cat_diff_ids = []
cat_diff_order_only = []
cat_diff_real = []
for wid in common:
    dc = dump[wid].get('categories', [])
    wc = wxr[wid].get('categories', [])
    if dc != wc:
        cat_diff_ids.append(wid)
        if sorted(map(str, dc)) == sorted(map(str, wc)):
            cat_diff_order_only.append(wid)
        else:
            cat_diff_real.append(wid)
print(f"\ncategories differing rows: {len(cat_diff_ids)}")
print(f"  order-only (same set, diff order): {len(cat_diff_order_only)}")
print(f"  real set differences: {len(cat_diff_real)}" + (f" e.g. {cat_diff_real[:10]}" if cat_diff_real else ""))

# other fields
for field in ['author_id','date','status','tags','thumbnail_id','title','slug','excerpt','modified','permalink','type']:
    diffs = [wid for wid in common if dump[wid].get(field) != wxr[wid].get(field)]
    print(f"{field} differing rows: {len(diffs)}" + (f" e.g. {diffs[:5]}" if diffs else ""))
