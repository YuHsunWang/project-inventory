"""Check README links and translation parity offline: python3 tests/check_readmes.py."""
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
FILES = ("README.md", "README.zh-TW.md", "README.zh-CN.md")
INSTALL_SENTENCE = ("Install project-inventory: read "
                    "https://raw.githubusercontent.com/YuHsunWang/project-inventory/main/INSTALL.md "
                    "and follow it.")


def parse(text):
    """Extract headings and fenced blocks without treating code as Markdown."""
    headings, blocks, prose = [], [], []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\n"))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                blocks.append((info, "".join(body)))
                fence = None
            else:
                body.append(line)
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            info, body = marker[2].strip(), []
        else:
            prose.append(line)
            heading = re.match(r"^ {0,3}(#{1,6}) +(.+?)(?: +#+)?$", line.rstrip("\n"))
            if heading:
                headings.append((len(heading[1]), heading[2]))
    assert fence is None, "unclosed fenced block"
    return headings, blocks, "".join(prose)


def github_slugs(headings):
    """GitHub heading IDs: lowercase, strip markup/punctuation, suffix duplicates."""
    used = set()
    for _, heading in headings:
        heading = re.sub(r"<[^>]*>", "", heading)
        heading = re.sub(r"!?\[([^]]*)\]\([^)]*\)", r"\1", heading)
        heading = heading.lower().replace("`", "")
        base = "".join(c for c in heading if c in " -_" or unicodedata.category(c)[0] in "LNM").replace(" ", "-")
        slug, suffix = base, 0
        while slug in used:
            suffix += 1
            slug = f"{base}-{suffix}"
        used.add(slug)
    return used


def main():
    parsed = {name: parse((ROOT / name).read_text(encoding="utf-8")) for name in FILES}
    errors, relative, anchors = [], 0, 0
    for name, (headings, blocks, prose) in parsed.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        # The paste instruction must be first in Install, before method subsections.
        install_section = re.search(r"^## (?:Install|安裝|安装)\n(.*?)(?=^### |^## |\Z)",
                                    text, re.M | re.S)
        if not install_section or f"> {INSTALL_SENTENCE}" not in install_section[1]:
            errors.append(f"{name}: missing agent install sentence at start of Install")
        if not (ROOT / "INSTALL.md").is_file():
            errors.append(f"{name}: missing INSTALL.md")
        if re.search(r"star\s+history|patreon", text, re.I):
            errors.append(f"{name}: forbidden text")
        for raw in re.findall(r"\]\(([^)\n]+)\)", prose):
            target = raw.strip().strip("<>")
            link = urlsplit(target)
            if link.scheme or link.netloc:
                continue
            path = ROOT / unquote(link.path) if link.path else ROOT / name
            if link.path:
                relative += 1
                if not path.is_file():
                    errors.append(f"{name}: missing relative file {target}")
                    continue
            if link.fragment:
                anchors += 1
                target_headings = parse(path.read_text(encoding="utf-8"))[0]
                if unquote(link.fragment) not in github_slugs(target_headings):
                    errors.append(f"{name}: missing anchor {target}")
        if "說明書.md" not in re.findall(r"\]\(([^)\n]+)\)", prose):
            errors.append(f"{name}: missing detailed manual link")
    baseline = parsed[FILES[0]]
    section_count = sum(level == 2 for level, _ in baseline[0])
    commands = [block for block in baseline[1] if block[0] in ("sh", "bash", "shell")]
    # Stronger than set equality: translations must preserve block order and duplicates.
    for name in FILES[1:]:
        headings, blocks, _ = parsed[name]
        if sum(level == 2 for level, _ in headings) != section_count:
            errors.append(f"{name}: level-2 section count differs")
        if blocks != baseline[1]:
            errors.append(f"{name}: fenced blocks differ")
        # Preserve every table's number of columns and data rows across languages.
        def tables(prose):
            runs = re.findall(r"(?:^\|.*\|\n)+", prose, re.M)
            return [tuple(len(re.split(r"(?<!\\)\|", row)) for row in run.splitlines()) for run in runs]
        if tables(parsed[name][2]) != tables(baseline[2]):
            errors.append(f"{name}: table structure differs")
    if errors:
        print("FAILED README checks:\n" + "\n".join(errors))
        return 1
    print(f"README checks: 3 files; {relative} relative links and {anchors} anchors OK; forbidden text absent.")
    print(f"Parity: {section_count} level-2 sections each; {len(commands)} command blocks and {len(baseline[1])} total fenced blocks identical; table structures match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
