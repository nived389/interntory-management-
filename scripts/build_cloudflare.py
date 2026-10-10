"""Build a public-only Pages bundle. Never publish the repository root."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
out = root / 'dist-cloudflare'
if out.exists():
    shutil.rmtree(out)
out.mkdir()
shutil.copytree(root / 'static', out / 'static')
shutil.copy2(root / 'static/index.html', out / 'index.html')
shutil.copy2(root / 'static/sw.js', out / 'sw.js')
shutil.copy2(root / 'deploy/cloudflare-worker.js', out / '_worker.js')
(out / '_routes.json').write_text('{"version":1,"include":["/*"],"exclude":["/static/*","/sw.js"]}\n')
print('Built public assets and authenticated backend gateway.')
