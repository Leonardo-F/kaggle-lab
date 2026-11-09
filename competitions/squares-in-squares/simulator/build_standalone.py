"""Reproducible offline HTML build using only the Python standard library."""
from pathlib import Path


def build() -> Path:
    root = Path(__file__).resolve().parent
    html = (root / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<link rel="stylesheet" href="styles.css">', '<style>\n' + (root / 'styles.css').read_text(encoding='utf-8') + '\n</style>')
    for name in ('packing-core.js', 'app.js'):
        html = html.replace(f'  <script src="{name}" defer></script>\n', '')
    scripts = '\n'.join((root / name).read_text(encoding='utf-8') for name in ('packing-core.js', 'app.js'))
    html = html.replace('</body>', '<script>\n' + scripts + '\n</script>\n</body>')
    output = root / 'SquarePackingStudio-standalone.html'
    output.write_text(html, encoding='utf-8')
    return output


if __name__ == '__main__':
    print(build())
