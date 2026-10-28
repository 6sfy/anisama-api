"""Garde-fous sur les assets web (navigation + couche a11y)."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "src" / "web"


def test_a11y_loaded_after_script():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'src="script.js"' in html
    assert 'src="a11y.js"' in html
    assert html.index('src="script.js"') < html.index('src="a11y.js"')


def test_a11y_navigation_is_self_contained():
    js = (WEB / "a11y.js").read_text(encoding="utf-8")
    # showPage est redéfini par a11y.js : il ne dépend pas de window.showPage
    assert "window.showPage =" in js
    # window.history : script.js déclare `let history` (historique terminal)
    assert "window.history.pushState" in js
    assert not re.search(r"(?<!window\.)history\.pushState", js)


def test_docs_have_no_inline_script_handlers():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "onclick=" not in html
    assert "data-page=" in html
