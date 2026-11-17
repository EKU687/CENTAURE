# =============================================================================
# SERVICE PDF PURE PYTHON (aucune dépendance externe)
# Génère le bulletin SITREP en PDF "pro" (A4, Helvetica, WinAnsiEncoding) :
# bandeau d'en-tête, encadré d'infos, sections colorées, pied de page paginé.
# Envoyé en pièce jointe de l'e-mail Brevo.
# =============================================================================

import re
import textwrap
from datetime import datetime
from typing import Dict, Any, List, Tuple

PAGE_W, PAGE_H = 595, 842  # A4 en points
MARGIN = 50
HEADER_H = 46
FOOTER_H = 52
BODY_SIZE = 10
LINE_H = 14
WRAP_WIDTH = 92

# Palette (RGB 0-1)
NAVY = (0.059, 0.090, 0.165)      # #0f172a (bandeau, comme l'e-mail)
BLUE = (0.145, 0.345, 0.839)      # #2563eb (sections)
AMBER = (0.851, 0.463, 0.027)     # #d97706 (points d'attention)
GREEN = (0.024, 0.663, 0.412)     # #059669 (actions)
PURPLE = (0.486, 0.278, 0.910)    # #7c3aed (échéance)
DARK = (0.067, 0.094, 0.153)      # #111827 (texte)
GRAY = (0.420, 0.463, 0.545)      # #6b7280 (gris)
LIGHT_BG = (0.937, 0.953, 0.976)  # #eef2f7 (encadré infos)
RED = (0.800, 0.200, 0.200)       # diffusion restreinte


def _normalize(text: str) -> str:
    """Garde uniquement ce qui passe en latin-1 (WinAnsi) : ponctuation usuelle
    mappée, emojis et autres caractères exotiques supprimés (pas de '?' moches)."""
    s = (
        str(text)
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u00a0", " ")
    )
    s = s.encode("latin-1", "ignore").decode("latin-1")
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def _esc(text: str) -> str:
    """Échappe une chaîne pour un littéral PDF ( ).
    (la normalisation latin-1 est faite en amont, à la source)"""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb(c: Tuple[float, float, float]) -> str:
    return f"{c[0]:.3f} {c[1]:.3f} {c[2]:.3f}"


def _text_op(x: float, y: float, text: str, font: str, size: float, color) -> str:
    return (
        f"{_rgb(color)} rg BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({_esc(text)}) Tj ET"
    )


def _text_right_op(y: float, text: str, font: str, size: float, color) -> str:
    width = len(_normalize(text)) * size * 0.52
    x = PAGE_W - MARGIN - width
    return _text_op(x, y, text, font, size, color)


def _rect_op(x: float, y: float, w: float, h: float, color) -> str:
    return f"{_rgb(color)} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f"


def _line_op(x1: float, y1: float, x2: float, y2: float, color, width: float = 1.0) -> str:
    return f"{_rgb(color)} RG {width} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S"


# kinds: "title" (16 gras navy, 22pt), "sect" (11 gras coloré + filet, 30pt),
#        "body" (10, LINE_H), "gap" (8pt)
def _logical_lines(crise_data: Dict[str, Any], sitrep_data: Dict[str, Any]) -> List[Tuple[str, str, tuple]]:
    """Lignes logiques (texte, kind, couleur) avant wrapping/pagination."""
    code = str(crise_data.get("code_crise", "CRISE"))
    titre = str(crise_data.get("titre", "Sans titre"))
    num = str(sitrep_data.get("numero_sitrep", "1"))
    redacteur = str(sitrep_data.get("redacteur", "N/A"))
    horodatage = str(sitrep_data.get("horodatage_fmt", "N/A"))
    gen_le = datetime.now().strftime("%d/%m/%Y %H:%M")

    out: List[Tuple[str, str, tuple]] = [
        (f"SITREP #{num} — {code}", "title", NAVY),
        (titre, "subtitle", DARK),
        (f"Crise : {code} — {titre}", "meta", GRAY),
        (f"Rédacteur : {redacteur}  |  Horodatage : {horodatage}  |  Édité le : {gen_le}", "meta", GRAY),
        ("gap", "gap", GRAY),
        ("SYNTHÈSE DE LA SITUATION", "sect", BLUE),
        (str(sitrep_data.get("synthese_situation") or "Aucune synthèse."), "body", DARK),
    ]
    if sitrep_data.get("points_attention"):
        out += [
            ("gap", "gap", GRAY),
            ("POINTS D'ATTENTION / ARBITRAGES SG", "sect", AMBER),
            (str(sitrep_data["points_attention"]), "body", DARK),
        ]
    if sitrep_data.get("actions_engagees"):
        out += [
            ("gap", "gap", GRAY),
            ("ACTIONS ENGAGÉES", "sect", GREEN),
            (str(sitrep_data["actions_engagees"]), "body", DARK),
        ]
    if sitrep_data.get("prochaine_echeance"):
        out += [
            ("gap", "gap", GRAY),
            ("PROCHAINE ÉCHÉANCE / RÉUNION", "sect", PURPLE),
            (str(sitrep_data["prochaine_echeance"]), "body", DARK),
        ]
    out += [
        ("gap", "gap", GRAY),
        ("Document généré automatiquement par le Cockpit CENTAURE.", "meta", GRAY),
    ]
    return [(_normalize(t), k, c) for t, k, c in out]


_LIST_SPLIT = re.compile(r"(?=\d+\.\s)")


def _split_body(text: str) -> List[str]:
    """Découpe un texte 'body' : chaque ligne source (\n) et chaque élément
    de liste numérotée ('1. ', '2. '...) démarre une nouvelle ligne."""
    parts: List[str] = []
    for raw in str(text).split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        for chunk in _LIST_SPLIT.split(raw):
            chunk = _normalize(chunk).strip()
            if chunk:
                parts.append(chunk)
    return parts


def _wrap(elements: List[Tuple[str, str, tuple]]) -> List[Tuple[str, str, tuple]]:
    """Retour à la ligne des lignes 'body' (listes numérotées éclatées,
    continuation indentée)."""
    wrapped: List[Tuple[str, str, tuple]] = []
    for text, kind, color in elements:
        if kind == "body" and text:
            for part in _split_body(text):
                for chunk in textwrap.wrap(
                    part, width=WRAP_WIDTH, subsequent_indent="    "
                ) or [""]:
                    wrapped.append((chunk, "body", color))
        else:
            wrapped.append((text, kind, color))
    return wrapped


def _line_height(kind: str) -> float:
    return {"title": 24, "subtitle": 18, "meta": 12, "sect": 26, "body": LINE_H, "gap": 8}[kind]


def build_sitrep_pdf(crise_data: Dict[str, Any], sitrep_data: Dict[str, Any]) -> bytes:
    """Génère le PDF du bulletin SITREP et retourne les octets du fichier."""
    num = str(sitrep_data.get("numero_sitrep", "1"))
    elements = _wrap(_logical_lines(crise_data, sitrep_data))

    # Pagination : budget de hauteur par page (bandeau + pied de page exclus).
    page_budget = PAGE_H - HEADER_H - FOOTER_H - 10
    first_budget = page_budget - 30  # le titre SITREP n'occupe que la 1re page

    pages: List[List[Tuple[str, str, tuple]]] = []
    current: List[Tuple[str, str, tuple]] = []
    budget = first_budget
    for el in elements:
        h = _line_height(el[1])
        if current and h > budget:
            pages.append(current)
            current = [el]
            budget = page_budget - h
        else:
            current.append(el)
            budget -= h
    if current:
        pages.append(current)
    if not pages:
        pages = [[("(vide)", "body", DARK)]]

    n_pages = len(pages)
    page_ids = [5 + 2 * i for i in range(n_pages)]
    content_ids = [6 + 2 * i for i in range(n_pages)]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)

    objs: List[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]

    gen_le = datetime.now().strftime("%d/%m/%Y %H:%M")

    for i, page_els in enumerate(pages):
        ops: List[str] = []

        # --- Bandeau d'en-tête (toutes pages) ---
        ops.append(_rect_op(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, NAVY))
        ops.append(
            _text_op(MARGIN, PAGE_H - HEADER_H + 17, _normalize(f"BULLETIN DE SITUATION — SITREP #{num}"), "F2", 13, (1, 1, 1))
        )
        ops.append(_text_right_op(PAGE_H - HEADER_H + 18, "CENTAURE | PCO", "F1", 9, (0.75, 0.82, 0.95)))

        # --- Pied de page (toutes pages) ---
        fy = FOOTER_H - 14
        ops.append(_line_op(MARGIN, fy + 12, PAGE_W - MARGIN, fy + 12, (0.80, 0.83, 0.87), 0.8))
        ops.append(_text_op(MARGIN, fy, _normalize(f"CENTAURE — auto le {gen_le}"), "F1", 8, GRAY))
        dr = "DIFFUSION RESTREINTE"
        dr_w = len(_normalize(dr)) * 8 * 0.52
        ops.append(_text_op((PAGE_W - dr_w) / 2, fy, dr, "F2", 8, RED))
        ops.append(_text_right_op(fy, f"Page {i + 1} / {n_pages}", "F1", 8, GRAY))

        # --- Contenu ---
        y = PAGE_H - HEADER_H - 24  # marge sous le bandeau
        for text, kind, color in page_els:
            h = _line_height(kind)
            if kind == "title":
                ops.append(_text_op(MARGIN, y - 16, text, "F2", 16, color))
            elif kind == "subtitle":
                ops.append(_text_op(MARGIN, y - 13, text, "F2", 12, color))
            elif kind == "meta":
                ops.append(_text_op(MARGIN, y - 9, text, "F1", 9, color))
            elif kind == "sect":
                ops.append(_text_op(MARGIN, y - 11, text, "F2", 11, color))
                ops.append(_line_op(MARGIN, y - 15, MARGIN + 130, y - 15, color, 1.4))
            elif kind == "body":
                ops.append(_text_op(MARGIN, y - 10, text, "F1", BODY_SIZE, color))
            # gap : rien, juste de la hauteur
            y -= h

        content = "\n".join(ops).encode("latin-1", "ignore")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_ids[i]} 0 R >>".encode()
        )
        objs.append(
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
        )

    # Assemblage + xref
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)
