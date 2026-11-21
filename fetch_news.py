#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds and build a static news.json for GitHub Pages.
Only titles, short summaries, attribution, dates and original links are included.
"""
import json, re, html, hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / 'sources.json'
OUTPUT = ROOT / 'news.json'
MAX_PER_SOURCE = 35
MAX_TOTAL = 180
ATOM = '{http://www.w3.org/2005/Atom}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', ' ', str(text))
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

def node_text(node):
    if node is None: return ''
    return clean(' '.join(t for t in node.itertext() if t))

def parse_date(entry):
    for key in ('pubDate','published','updated','date',ATOM+'published',ATOM+'updated'):
        raw = entry.find(key)
        if raw is not None:
            value = raw.text or node_text(raw)
            if not value: continue
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(value.strip())
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                try:
                    dt=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
                    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception: pass
    return ''

def get_text(entry, *names):
    for name in names:
        found=entry.find(name)
        value=node_text(found)
        if value: return value
    return ''

def get_link(entry):
    link=get_text(entry,'link')
    if link and urlparse(link).scheme in ('http','https'): return link
    for atom_link in entry.findall(ATOM+'link'):
        href=atom_link.attrib.get('href','')
        rel=atom_link.attrib.get('rel','alternate')
        if href and rel in ('alternate',''): return href
    return ''

def fetch_feed(source):
    req=urllib.request.Request(source['url'],headers={'User-Agent':'Mozilla/5.0 (compatible; LebanonNewsAggregator/1.0)','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urllib.request.urlopen(req,timeout=18) as response:
        raw=response.read(3_000_000)
    root=ET.fromstring(raw)
    entries=root.findall('.//item')
    if not entries: entries=root.findall('.//'+ATOM+'entry')
    results=[]
    for entry in entries[:MAX_PER_SOURCE]:
        title=get_text(entry,'title')
        description=get_text(entry,'description','summary',ATOM+'summary',CONTENT,ATOM+'content')
        link=get_link(entry)
        if title and link and urlparse(link).scheme in ('http','https'):
            description=description[:500]
            uid=hashlib.sha256((title+link).encode('utf-8')).hexdigest()[:16]
            results.append({'id':uid,'title':title,'description':description,'url':link,'source':source['name'],'date':parse_date(entry),'category':source.get('category','لبنان')})
    return results

def main():
    sources=json.loads(SOURCES_FILE.read_text(encoding='utf-8'))
    previous_ids=set()
    if OUTPUT.exists():
        try:
            previous=json.loads(OUTPUT.read_text(encoding='utf-8'))
            previous_ids={a.get('id') for a in previous.get('articles',[]) if a.get('id')}
        except Exception:
            pass
    all_articles=[]; failed=[]
    for source in sources:
        try:
            found=fetch_feed(source)
            all_articles.extend(found)
            print(f"OK {source['name']}: {len(found)}")
        except Exception as exc:
            failed.append(source['name'])
            print(f"SKIP {source['name']}: {exc}")
    unique=[]; seen=set()
    for a in all_articles:
        key=a['url'].split('#')[0].rstrip('/') or a['title'].strip().lower()
        if key in seen: continue
        seen.add(key); unique.append(a)
    unique.sort(key=lambda a:a.get('date') or '',reverse=True)
    latest=unique[:MAX_TOTAL]
    new_articles=[a for a in latest if a.get('id') not in previous_ids]
    payload={'updated':datetime.now(timezone.utc).isoformat(),'sources_total':len(sources),'sources_failed':failed,'articles':latest,'new_articles':new_articles}
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"Saved {len(payload['articles'])} stories; {len(new_articles)} new stories. Failed feeds: {len(failed)}")
if __name__=='__main__': main()
