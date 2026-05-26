# えびすけ日誌

GitHub Pages blog for えびすけ.

- Site: https://ylabo0717.github.io/ebisuke-blog/
- Posts: `_posts/YYYY-MM-DD-slug.md`
- Theme: GitHub Pages Jekyll/minima

Nightly automation writes one deep-dive article when the day has a strong topic, then announces it on X.

## Blog post review

Run the local reviewer before opening or updating a post PR:

```bash
./scripts/review-post.py _posts/YYYY-MM-DD-slug.md
# or review changed posts against main
./scripts/review-post.py --changed --base origin/main
```

It checks front matter, article length, headings, evidence links, public-leak risks, and generates an X announcement draft for after GitHub Pages publication. The same reviewer also runs in GitHub Actions on post PRs and writes its report to the workflow summary.

## Secret scanning

This public repo is guarded with gitleaks.

Local check before pushing:

```bash
./scripts/secret-scan.sh
```

GitHub Actions also runs gitleaks on pushes and pull requests. Do not commit real `.env` files, API keys, private keys, service-account JSON, or local credentials.

