"""Use fallback fonts for the offline sample browser checks."""
from pathlib import Path


def offline_fonts(home):
    # Offline browser fixtures exercise the CSS fallback fonts; CDN availability
    # is a separate live acceptance concern, not part of the zero-service gate.
    import re
    page = Path(home) / 'out/index.html'
    page.write_text(re.sub(r'<link[^>]+href="https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', page.read_text()))


if __name__ == '__main__':
    import sys
    offline_fonts(sys.argv[1])
