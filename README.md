# أخبار بلا هراء

Arabic RTL news aggregator for GitHub Pages. The site displays article headlines, short feed summaries, publisher names, timestamps, and links to the original publisher. It does **not** copy full articles.

## Files
- `index.html`, `style.css`, `news.js`: static website.
- `sources.json`: feed list (edit to add/remove RSS/Atom sources).
- `fetch_news.py`: feed importer; writes `news.json`.
- `.github/workflows/update-news.yml`: scheduled feed refresh every 15 minutes and manual run.

## Publish
1. Create a GitHub repository and upload all project files, including the hidden `.github` folder.
2. Go to **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**.
3. Run **Actions → Update news feeds → Run workflow** once to create/update `news.json`.
4. Go to **Settings → Pages**; deploy from branch `main`, folder `/ (root)`.

The site URL is `https://YOUR-USERNAME.github.io/REPOSITORY/`.

## Sources and limitations
Feed endpoints can change or block automated requests. A feed failure is logged and skipped without stopping other feeds. Internet connectivity was unavailable in the build environment, so feeds could not all be live-tested; verify them in the Actions log after the first run. Respect each publisher's terms and attribution requirements. Headlines, short descriptions, source attribution, and original links only are collected.
