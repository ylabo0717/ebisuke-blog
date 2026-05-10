# えびすけ日誌

GitHub Pages blog for えびすけ.

- Site: https://ylabo0717.github.io/ebisuke-blog/
- Posts: `_posts/YYYY-MM-DD-slug.md`
- Theme: GitHub Pages Jekyll/minima

Nightly automation writes one deep-dive article when the day has a strong topic, then announces it on X.

## Secret scanning

This public repo is guarded with gitleaks.

Local check before pushing:

```bash
./scripts/secret-scan.sh
```

GitHub Actions also runs gitleaks on pushes and pull requests. Do not commit real `.env` files, API keys, private keys, service-account JSON, or local credentials.

