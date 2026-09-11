#!/usr/bin/env python3
"""
F16: Verify legacy URLs against the live Jakarta site.

Stratified sample of 200+ URLs with:
- Throttling (2-3 seconds between requests)
- Realistic User-Agent
- Retry timeouts once before marking as unknown
- Record status: 200 / 301 (+ target) / 404 / timeout
- Report: resolved / redirected / 404 / unknown
"""

import json
import time
import random
from pathlib import Path
from typing import Optional
from collections import defaultdict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Site configuration
LIVE_SITE = "https://nowjakarta.co.id"
# Path from engine/packages/permalinks/verify_urls.py -> project root
# resolve().parent gives us the permalinks directory
# parents[0] = packages, parents[1] = engine, parents[2] = now! (project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parents[2]
PERMALINK_MAP_PATH = PROJECT_ROOT / "jakarta" / "content" / "extracted" / "permalink_map.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "jakarta" / "content" / "extracted" / "url_verification.jsonl"


def create_session() -> requests.Session:
    """Create a requests session with reasonable timeouts and retries."""
    session = requests.Session()

    # Set a realistic User-Agent
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    # Set timeouts
    session.timeout = 10

    return session


def load_permalink_map() -> list[dict]:
    """Load the permalink map from JSONL file."""
    urls = []
    with open(PERMALINK_MAP_PATH) as f:
        for line in f:
            if line.strip():
                urls.append(json.loads(line))
    return urls


def create_stratified_sample(urls: list[dict], sample_size: int = 200) -> list[dict]:
    """Create a stratified sample from the URL list.

    Includes:
    - All redirection_plugin URLs (38)
    - All _wp_old_slug URLs (149)
    - Random sample of current_post_name to reach sample_size
    """
    by_source = defaultdict(list)
    for url in urls:
        by_source[url["source"]].append(url)

    sample = []

    # Include all redirection_plugin URLs (these are the riskiest)
    sample.extend(by_source["redirection_plugin"])
    print(f"  Added all {len(by_source['redirection_plugin'])} redirection_plugin URLs")

    # Include all _wp_old_slug URLs (these are commonly missed)
    sample.extend(by_source["_wp_old_slug"])
    print(f"  Added all {len(by_source['_wp_old_slug'])} _wp_old_slug URLs")

    # Add random current_post_name URLs to reach sample_size
    remaining = sample_size - len(sample)
    if remaining > 0:
        current_posts = random.sample(by_source["current_post_name"], min(remaining, len(by_source["current_post_name"])))
        sample.extend(current_posts)
        print(f"  Added {len(current_posts)} random current_post_name URLs")

    # Shuffle the sample to spread requests across different categories
    random.shuffle(sample)
    return sample


def verify_url(session: requests.Session, url: str, retry: bool = False) -> dict:
    """Verify a single URL and return status info.

    Returns a dict with:
    - status: "200" | "301" | "302" | "404" | "timeout" | "error"
    - target: (only for redirects) the Location header value
    - http_status: the actual HTTP status code (if available)
    """
    try:
        # Use allow_redirects=False to capture redirect status, not the final destination
        response = session.get(
            url,
            allow_redirects=False,
            timeout=10
        )

        if response.status_code == 200:
            return {"status": "200", "http_status": 200}
        elif response.status_code in (301, 302, 307, 308):
            target = response.headers.get("Location", "")
            return {
                "status": "301" if response.status_code in (301, 307) else "302",
                "http_status": response.status_code,
                "target": target
            }
        elif response.status_code == 404:
            return {"status": "404", "http_status": 404}
        else:
            return {"status": "error", "http_status": response.status_code}

    except requests.Timeout:
        if retry:
            # Timeout already retried, record as unknown
            return {"status": "timeout", "retried": True}
        else:
            return {"status": "timeout", "retried": False}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def main() -> None:
    """Run the URL verification."""
    print("F16: Verifying legacy URLs from permalink_map.jsonl")
    print(f"Live site: {LIVE_SITE}")
    print()

    # Load and sample URLs
    print("Loading URLs...")
    all_urls = load_permalink_map()
    print(f"Total URLs: {len(all_urls)}")
    print()

    print("Creating stratified sample...")
    sample = create_stratified_sample(all_urls, sample_size=200)
    print(f"Sample size: {len(sample)}")
    print()

    # Verify URLs
    print("Verifying URLs (throttled to 1 per 2-3 seconds)...")
    session = create_session()
    results = []

    status_counts = defaultdict(int)
    four_oh_fours = []

    for i, entry in enumerate(sample, 1):
        legacy_url = entry["legacy_url"]
        full_url = LIVE_SITE + legacy_url

        # Throttle requests
        if i > 1:
            wait_time = random.uniform(2.0, 3.0)
            time.sleep(wait_time)

        # Try once, then retry timeout if needed
        result = verify_url(session, full_url, retry=False)
        if result.get("status") == "timeout":
            print(f"  [{i}/{len(sample)}] {legacy_url[:60]:60s} TIMEOUT (retrying...)")
            time.sleep(2)
            result = verify_url(session, full_url, retry=True)

        # Log result
        entry_result = {
            **entry,
            "full_url": full_url,
            "verification": result
        }
        results.append(entry_result)

        # Update counts
        status = result.get("status")
        status_counts[status] += 1

        if status == "404":
            four_oh_fours.append(entry_result)
            print(f"  [{i}/{len(sample)}] {legacy_url[:60]:60s} 404 ❌")
        elif status == "301":
            target = result.get("target", "")[:50]
            print(f"  [{i}/{len(sample)}] {legacy_url[:60]:60s} 301 → {target}...")
        elif status == "200":
            print(f"  [{i}/{len(sample)}] {legacy_url[:60]:60s} 200 ✓")
        else:
            print(f"  [{i}/{len(sample)}] {legacy_url[:60]:60s} {status}")

    session.close()

    # Write results
    output_path = OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    print()
    print("=" * 70)
    print("VERIFICATION RESULTS")
    print("=" * 70)

    # Count statuses
    resolved = status_counts.get("200", 0)
    redirected = status_counts.get("301", 0) + status_counts.get("302", 0)
    not_found = status_counts.get("404", 0)
    unknown = status_counts.get("timeout", 0) + status_counts.get("error", 0)

    print()
    print(f"Sample verified: {len(sample)} URLs")
    print(f"  Resolved (200):     {resolved}")
    print(f"  Redirected (3xx):   {redirected}")
    print(f"  Not Found (404):    {not_found}")
    print(f"  Unknown/Timeout:    {unknown}")
    print()

    if four_oh_fours:
        print(f"URLs that returned 404 ({len(four_oh_fours)}):")
        for entry in four_oh_fours:
            print(f"  - {entry['legacy_url']}")
            print(f"    Source: {entry['source']}, WP ID: {entry['wp_id']}")
        print()

    # Group 404s by source
    four_oh_four_by_source = defaultdict(list)
    for entry in four_oh_fours:
        four_oh_four_by_source[entry["source"]].append(entry)

    if four_oh_four_by_source:
        print("404s by source type:")
        for source, entries in sorted(four_oh_four_by_source.items()):
            print(f"  {source}: {len(entries)}")

    print()
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    main()
