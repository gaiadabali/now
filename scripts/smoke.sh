#!/usr/bin/env bash
#
# Live smoke test for both cities.
#
# Written after a deploy that passed every check I had run and was still
# broken for the user. The checks I had were all "does this URL return 200" —
# and the failure (sharp missing from the runtime image) only appears on a
# path that optimises an image, which none of them touched.
#
# So this exercises what a reader and an editor actually do: load a home page,
# follow an article, fetch the images on it, open a section, reach the admin.
# A 200 with a broken page is a failure here, not a pass.
#
#   scripts/smoke.sh                      # both cities, live
#   scripts/smoke.sh http://127.0.0.1:4311 http://127.0.0.1:4315
set -uo pipefail

JAKARTA="${1:-https://now-jakarta.gaiada.com}"
BALI="${2:-https://now-bali.gaiada.com}"
TIMEOUT=30

pass=0; fail=0
ok()   { printf '  \033[32mok\033[0m   %s\n' "$*"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; fail=$((fail+1)); }
head_() { curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$1" 2>/dev/null; }
body() { curl -s --max-time "$TIMEOUT" "$1" 2>/dev/null; }

smoke_city() {
  local base="$1" name="$2" expect_title="$3"
  printf '\n\033[36m== %s (%s)\033[0m\n' "$name" "$base"

  local home; home="$(body "$base/")"
  [ -n "$home" ] || { bad "$name homepage returned nothing"; return; }

  grep -q "<title>$expect_title</title>" <<<"$home" \
    && ok "title is $expect_title" \
    || bad "title is not $expect_title (got: $(grep -oE '<title>[^<]*' <<<"$home" | head -1))"

  # Article links. The fixture era had 26; a real city has thousands, so a
  # low count here means the data layer fell back to something.
  local links count
  links="$(grep -oE 'href="/[a-z0-9-]{15,}"' <<<"$home" | sed 's/href="//;s/"//' | sort -u)"
  count="$(wc -l <<<"$links" | tr -d ' ')"
  [ "$count" -ge 8 ] && ok "$count distinct article links on the home page" \
                     || bad "only $count article links — is this real content?"

  # Follow one through and confirm it renders as an article, not a 404 shell.
  local first art
  first="$(head -1 <<<"$links")"
  if [ -n "$first" ]; then
    local code; code="$(head_ "$base$first")"
    art="$(body "$base$first")"
    # Status first, then real content. Do NOT grep for the 404 page's text:
    # Next embeds the not-found boundary component in every page's RSC
    # payload, so that string is present on perfectly healthy pages. That
    # exact heuristic produced a false failure on an article that was fine.
    if [ "$code" != "200" ]; then
      bad "article $first returned HTTP $code"
    elif ! grep -qE '<h1[^>]*>.{10,}' <<<"$art"; then
      bad "article $first has no headline — is it rendering?"
    elif [ "$(grep -cE '<p[^>]*>.{60,}' <<<"$art")" -lt 1 ]; then
      bad "article $first has a headline but no body copy"
    else
      ok "article $first renders with headline and body"
    fi
  fi

  # IMAGES. This is the check that was missing: fetch them, do not just find
  # them in the markup. next/image rewrites through /_next/image, which is
  # what invokes sharp.
  local imgs img_total=0 img_ok=0
  imgs="$(grep -oE 'src="(/_next/image\?[^"]+|https://[^"]+\.(jpg|jpeg|png|webp|avif))"' <<<"$art" \
          | sed 's/src="//;s/"$//' | sed 's/&amp;/\&/g' | sort -u | head -4)"
  if [ -z "$imgs" ]; then
    bad "no images found on $first"
  else
    while IFS= read -r src; do
      [ -z "$src" ] && continue
      img_total=$((img_total+1))
      local url="$src"
      [[ "$src" == /* ]] && url="$base$src"
      local code; code="$(head_ "$url")"
      [ "$code" = "200" ] && img_ok=$((img_ok+1)) || printf '       image %s -> HTTP %s\n' "${src:0:70}" "$code"
    done <<<"$imgs"
    [ "$img_ok" -eq "$img_total" ] && ok "$img_ok/$img_total images load" \
                                   || bad "$img_ok/$img_total images load"
  fi

  # DOCUMENT STRUCTURE. A page with two <html> elements returns a perfectly
  # good 200 and then dies in the browser with "Application error: a
  # client-side exception has occurred" — React cannot hydrate a nested
  # document. curl never runs React, so every server-side check passed while
  # the admin was unusable. This is the cheap proxy for that whole class of
  # bug, and it is here because it actually happened: Payload's RootLayout
  # renders its own <html>, and nesting it under the reader's root layout
  # produced <html> x2 on every /team-editor page.
  local doc_bad=0
  for path in "/" "/team-editor" "/team-editor/login"; do
    local page_html n_html n_body
    page_html="$(body "$base$path")"
    n_html="$(grep -o '<html' <<<"$page_html" | wc -l | tr -d ' ')"
    n_body="$(grep -o '<body' <<<"$page_html" | wc -l | tr -d ' ')"
    if [ "$n_html" != "1" ] || [ "$n_body" != "1" ]; then
      bad "$path has <html>x$n_html <body>x$n_body — will not hydrate"
      doc_bad=1
    fi
  done
  [ "$doc_bad" -eq 0 ] && ok "one <html>/<body> on reader, admin and login"

  # FAVICON. There was none at all: /favicon.ico 404'd on both cities and the
  # tab showed a blank page icon. It is per-city (one image, two cities), so a
  # static app/icon file cannot serve it — the check is that the link is in
  # the document AND the asset actually loads.
  local icon
  icon="$(grep -oE '<link[^>]*rel="icon"[^>]*>' <<<"$home" | grep -oE 'href="[^"]+"' | head -1 | sed 's/href="//;s/"$//')"
  if [ -z "$icon" ]; then
    bad "$name ships no <link rel=icon>"
  else
    local icode; icode="$(head_ "$base$icon")"
    [ "$icode" = "200" ] && ok "favicon $icon loads" || bad "favicon $icon -> HTTP $icode"
  fi

  # /culture is a taxonomy-backed section, not a primaryType filter — an empty
  # one would mean the term lookup silently returned nothing.
  local cul cul_n
  cul="$(body "$base/culture")"
  cul_n="$(grep -oE 'href="/[a-z0-9-]{15,}"' <<<"$cul" | sort -u | wc -l | tr -d ' ')"
  [ "$cul_n" -ge 5 ] && ok "/culture lists $cul_n articles"                      || bad "/culture lists only $cul_n articles — did the term lookup fail?"

  # ESCAPED MARKUP IN THE BODY. The archive stores paragraphs as HTML and the
  # reader rendered them with `<p>{p}</p>`, so React escaped them and readers
  # saw `<strong>Open daily from 5.30pm</strong>` and whole mailto anchors in
  # the middle of the copy. Every article with any formatting was affected.
  if grep -qE '&lt;(strong|em|a |br|mark)' <<<"$art"; then
    bad "$first shows escaped HTML tags as text"
  else
    ok "article body renders markup rather than printing it"
  fi

  # FACET ARITHMETIC. The chips are counts; if they do not sum to All, the
  # page is visibly wrong. Bali dining read ALL 1251 over chips summing to
  # 739, because the 512 articles with no format were counted in the total and
  # then filtered out of the chip row.
  # The first count in document order is All; the rest are the chips. Read
  # positionally rather than by matching the word "All", which is a label and
  # may be styled or translated. awk, not bc: bc is not in Git Bash.
  local dining counts all_n chip_sum
  dining="$(body "$base/dining")"
  counts="$(grep -oE 'class="facet__count">[0-9]+' <<<"$dining" | grep -oE '[0-9]+$')"
  all_n="$(head -1 <<<"$counts")"
  chip_sum="$(tail -n +2 <<<"$counts" | awk '{s+=$1} END {print s+0}')"
  if [ -z "$all_n" ] || [ -z "$counts" ]; then
    bad "could not read facet counts on /dining"
  elif [ "$all_n" = "$chip_sum" ]; then
    ok "facet chips sum to All ($all_n)"
  else
    bad "facet chips sum to $chip_sum but All says $all_n"
  fi

  # PAGINATION. Half the archive used to be unreachable by browsing — a
  # section showed a fixed twelve of its several hundred articles, and
  # untyped articles had no section at all. Two things must hold: a later
  # page must return DIFFERENT articles (a pager that silently ignores ?page=
  # returns 200 and looks fine), and /unclassified must be populated, since
  # that is where a quarter of the archive lives until editors re-file it.
  local p1 p2 shared
  p1="$(body "$base/dining" | grep -oE 'href="/[a-z0-9-]{15,}"' | sort -u)"
  p2="$(body "$base/dining?page=2" | grep -oE 'href="/[a-z0-9-]{15,}"' | sort -u)"
  if [ -z "$p2" ]; then
    bad "/dining?page=2 has no articles"
  else
    shared="$(comm -12 <(printf '%s
' "$p1") <(printf '%s
' "$p2") | wc -l | tr -d ' ')"
    [ "$shared" -eq 0 ] && ok "/dining page 2 is a different slice of the archive"                         || bad "/dining page 2 repeats $shared articles from page 1"
  fi

  local unc
  unc="$(body "$base/unclassified" | grep -oE 'href="/[a-z0-9-]{15,}"' | sort -u | wc -l | tr -d ' ')"
  [ "$unc" -ge 10 ] && ok "/unclassified lists $unc articles"                     || bad "/unclassified lists only $unc — untyped articles are still unreachable"

  # Section index.
  local sec; sec="$(head_ "$base/dining")"
  [ "$sec" = "200" ] && ok "/dining returns 200" || bad "/dining returns $sec"

  # Admin. 200 or a redirect to login are both fine; 404 or 500 are not.
  local adm; adm="$(head_ "$base/team-editor")"
  case "$adm" in
    200|302|307) ok "/team-editor returns $adm" ;;
    *)           bad "/team-editor returns $adm" ;;
  esac

  local lg; lg="$(head_ "$base/team-editor/login")"
  case "$lg" in
    200|302|307) ok "/team-editor/login returns $lg" ;;
    *)           bad "/team-editor/login returns $lg" ;;
  esac

  # UNRESOLVED PAYLOAD COMPONENTS. A negative assertion, and the only marker
  # that discriminates a working admin from a blank one in bytes curl can see.
  #
  # Written after a deploy where every /team-editor route served 200 with
  # ~55 KB of valid HTML and an empty page. Supplying GARAGE_* at RUN time
  # switched on the s3Storage plugin, whose client component is resolved
  # through importMap.js — generated at BUILD time, in an image built without
  # those credentials. The entry was not there, the component rendered as
  # nothing, and Payload reported it only as a warning.
  #
  # Everything the obvious instinct reaches for is IDENTICAL in both states,
  # measured against captured broken/healthy pairs of two admin routes:
  #
  #                        login B/H      review B/H
  #     staff-login          5 / 5          0 / 0
  #     password            11 / 11        11 / 11
  #     Sign in              3 / 3          0 / 0
  #     <form                0 / 0          0 / 0     (client-rendered:
  #     <input               0 / 0          0 / 0      zero even when healthy)
  #     getFromImportMap     1 / 0          1 / 0     <- the only tell
  #
  # Nor does size: login broke LARGER (75717 vs 68159) and review broke
  # SMALLER (74920 vs 80267), so a "at least N bytes" check is not merely
  # weak, it is wrong in one direction or the other depending on the route.
  #
  # Deliberately NOT keyed on `storage-s3`, which also discriminates 3/0. That
  # would catch only the instance we have already had. This catches the class:
  # any Payload component that cannot be resolved from the manifest, whatever
  # registered it.
  #
  # What this CANNOT do: prove a person can sign in. The form is client
  # rendered, so curl never sees it in any state. Honest scope is "no
  # unresolved components, and a status line". For "the form works", drive a
  # browser — see scripts/smoke-browser.mjs.
  local ic route_html
  for route in "/team-editor" "/team-editor/login"; do
    route_html="$(body "$base$route")"
    ic="$(grep -c 'getFromImportMap' <<<"$route_html" || true)"
    if [ "${ic:-0}" -eq 0 ]; then
      ok "$route resolves every Payload component"
    else
      bad "$route has UNRESOLVED Payload components — it will render blank in a browser despite this 200"
    fi
  done

  # The admin is a client app; if its chunks 404 the page dies in the browser
  # while the server still reports 200 — exactly the failure mode reported.
  local adm_html chunk chunk_bad=0 chunk_n=0
  adm_html="$(body "$base/team-editor")"
  while IFS= read -r chunk; do
    [ -z "$chunk" ] && continue
    chunk_n=$((chunk_n+1))
    [ "$(head_ "$base$chunk")" = "200" ] || { chunk_bad=$((chunk_bad+1)); printf '       chunk %s missing\n' "${chunk:0:60}"; }
  done <<<"$(grep -oE 'src="/_next/static/[^"]+\.js"' <<<"$adm_html" | sed 's/src="//;s/"$//' | sort -u | head -6)"
  if [ "$chunk_n" -eq 0 ]; then
    bad "/team-editor shipped no client chunks"
  elif [ "$chunk_bad" -eq 0 ]; then
    ok "$chunk_n admin client chunks load"
  else
    bad "$chunk_bad of $chunk_n admin chunks are missing"
  fi

  printf '%s\n' "$links" > "/tmp/smoke-$name.links"
}

smoke_city "$JAKARTA" "jakarta" "NOW! Jakarta"
smoke_city "$BALI"    "bali"    "NOW! Bali"

# The two cities must not be showing the SAME FEED. This is the check the
# whole content migration existed to satisfy.
#
# A handful of shared URLs is expected and is NOT a failure: ARCHITECTURE.md
# §3.4 records that Jakarta's archive holds 111 "Bali Updates" articles which,
# under the region model, are Bali's. Who owns a story is an editorial call.
# What would be a bug is the two feeds being identical, which is what the
# fixture era did.
printf '
[36m== cross-city[0m
'
if [ -s /tmp/smoke-jakarta.links ] && [ -s /tmp/smoke-bali.links ]; then
  overlap="$(comm -12 /tmp/smoke-jakarta.links /tmp/smoke-bali.links | wc -l | tr -d ' ')"
  total="$(wc -l < /tmp/smoke-jakarta.links | tr -d ' ')"
  if [ "$overlap" -eq "$total" ]; then
    bad "both cities show the SAME $total articles — feeds are not differentiated"
  elif [ "$overlap" -eq 0 ]; then
    ok "the two feeds share no articles"
  else
    ok "feeds differ ($overlap of $total shared — §3.4 syndication, editorial)"
    comm -12 /tmp/smoke-jakarta.links /tmp/smoke-bali.links | sed 's/^/       shared: /'
  fi
fi

printf '\n\033[1m%d passed, %d failed\033[0m\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
