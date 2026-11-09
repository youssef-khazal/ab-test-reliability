"""Build the calculator page: inject demo/prior.json into demo/template.html -> demo/index.html.

    python scripts/build_demo.py

index.html is a complete static page (no server, no model): it can be opened directly in a browser or
published as a static Hugging Face Space together with demo/README.md.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
prior = (ROOT / "demo" / "prior.json").read_text(encoding="utf-8")
body = page.replace("/*PRIOR*/", prior)
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{color-scheme:light}body{margin:0}[hidden]{display:none!important}</style>\n')
title_end = body.index("</style>") + len("</style>")
html = head + body[:title_end] + "\n</head>\n<body>\n" + body[title_end:] + "\n</body>\n</html>\n"
(ROOT / "demo" / "index.html").write_text(html, encoding="utf-8")
print("wrote demo/index.html")
