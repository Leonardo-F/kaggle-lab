"""Build the offline studio with the exact CSV accepted by the scorer."""
import base64
import gzip
import hashlib
import json
import io
from pathlib import Path


def build() -> Path:
    root = Path(__file__).resolve().parent
    submissions = root.parent / 'submissions'
    version = json.loads((submissions / 'latest.json').read_text())
    csv = (submissions / version['csv']).read_bytes()
    report = json.loads((submissions / version['report']).read_text())
    digest = hashlib.sha256(csv).hexdigest()
    if not report['valid'] or report['puzzles'] != 1000 or report['csv_sha256'] != digest:
        raise ValueError('Rebuild the official certification for the current CSV first')

    html = (root / 'index.html').read_text(encoding='utf-8')
    styles = (root / 'styles.css').read_text(encoding='utf-8')
    html = html.replace('<link rel="stylesheet" href="styles.css">', f'<style>\n{styles}\n</style>')
    names = ('packing-core.js', 'bands.js', 'band-witnesses.js', 'app.js')
    for name in names:
        html = html.replace(f'  <script src="{name}" defer></script>\n', '')
    scripts = '\n'.join((root / name).read_text(encoding='utf-8') for name in names)
    # Stable gzip header across Python versions and operating systems.
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', compresslevel=9, mtime=0) as archive:
        archive.write(csv)
    payload = base64.b64encode(stream.getvalue()).decode('ascii')
    score = version['simulator_score']
    if version['csv'] != f'rectangular_core-score-{score}.csv' or f"{report['score_literal']:.9f}" != score:
        raise ValueError('The CSV name and the certification must agree with the simulator score')
    embedded = (f'<script id="certifiedCsv" type="application/octet-stream" '
                f'data-sha256="{digest}" data-score="{score}">{payload}</script>')
    html = html.replace('</body>', f'{embedded}\n<script>\n{scripts}\n</script>\n</body>')
    output = root / 'SquarePackingStudio-standalone.html'
    output.write_text(html, encoding='utf-8')
    return output


if __name__ == '__main__':
    print(build())
