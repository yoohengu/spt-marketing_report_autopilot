"""
output/insight_report.md -> output/insight_report.html 렌더러.

`.md`(정본)를 읽어 스타일이 입혀진 HTML 리포트를 생성한다. Claude가 .html을 따로 손으로 만들 필요 없이
.md만 갱신하면 이 스크립트가 같은 내용의 HTML을 다시 뽑아주므로 두 파일이 어긋날(드리프트) 일이 없다.

특정 채널명·날짜·수치를 하드코딩하지 않는다. 리포트의 "구조"(H2 섹션, 이슈/기획안 소제목, 배지,
표, KPI 표 등 template.md가 정한 형식)만 인식해 대응 컴포넌트로 변환하므로, 새 CSV로 내용이
전부 바뀌어도 동일하게 동작한다. 특별 처리에 걸리지 않는 블록은 일반 마크다운 규칙으로 렌더한다.

사용법:
    python src/render_html.py [md_path] [html_out]
    # md_path 생략 시 output/insight_report.md, html_out 생략 시 output/insight_report.html
    # regenerate.py로 .md를 갱신한 뒤 이어서 실행하면 HTML까지 최신화된다.
"""
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_MD = 'output/insight_report.md'
DEFAULT_HTML = 'output/insight_report.html'

BADGE_MAP = {'🟢': 'basic', '🟡': 'standard', '🔴': 'challenge'}
KPI_COLORS = ['blue', 'green', 'orange', 'purple']

CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif; background: #f4f5f7; color: #1a1a2e; line-height: 1.6; }
.container { max-width: 1080px; margin: 0 auto; padding: 40px 24px; }

.header { background: #fff; border-radius: 12px; padding: 32px 36px; margin-bottom: 24px; border-left: 5px solid #4361ee; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.header h1 { font-size: 22px; font-weight: 700; margin-bottom: 10px; }
.header-meta { font-size: 13px; color: #6c757d; display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 14px; }
.header-note { font-size: 12.5px; color: #888; background: #f8f9fa; border-radius: 8px; padding: 10px 14px; }
.legend { font-size: 12px; color: #888; margin-top: 6px; }

.section { background: #fff; border-radius: 12px; padding: 28px 32px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.section-title { font-size: 15px; font-weight: 700; padding-bottom: 14px; margin-bottom: 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.tag { display: inline-block; font-size: 10px; font-weight: 700; padding: 3px 9px; border-radius: 10px; }
.tag-basic { background: #e3f9e9; color: #1b7a3d; }
.tag-standard { background: #fff3cd; color: #8a6400; }
.tag-challenge { background: #ffe0e3; color: #c9323e; }

.note { font-size: 12.5px; color: #888; margin-bottom: 14px; }
.note-warn { font-size: 12px; color: #c9323e; margin-top: 12px; }

.conclusion { font-size: 14.5px; background: #f0f3ff; border-left: 4px solid #4361ee; border-radius: 0 8px 8px 0; padding: 14px 18px; margin-bottom: 20px; }
.conclusion b { color: #2b3a99; }

.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi { border-radius: 8px; padding: 16px; text-align: center; background: #f8f9fa; }
.kpi-n { font-size: 21px; font-weight: 800; }
.kpi-l { font-size: 12px; margin-top: 4px; color: #666; }
.kpi-blue .kpi-n { color: #4361ee; }
.kpi-green .kpi-n { color: #2d6a4f; }
.kpi-purple .kpi-n { color: #7048e8; }
.kpi-orange .kpi-n { color: #e76f51; }

.subsection { margin-bottom: 22px; }
.subsection:last-child { margin-bottom: 0; }
.subsection h3 { font-size: 13.5px; font-weight: 700; margin-bottom: 10px; }
h3 { font-size: 13.5px; font-weight: 700; margin: 16px 0 10px; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #f8f9fa; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: #6c757d; padding: 9px 12px; text-align: left; border-bottom: 2px solid #e9ecef; }
tbody td { padding: 9px 12px; border-bottom: 1px solid #f0f2f5; vertical-align: middle; }
tbody tr.total td { font-weight: 800; background: #f8f9fa; border-top: 2px solid #e9ecef; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.rank1 { color: #2d6a4f; font-weight: 700; }
.rank-low { color: #c9323e; font-weight: 700; }
.interp { font-size: 13px; color: #555; margin-top: 12px; background: #f8f9fa; border-radius: 8px; padding: 12px 16px; }

.issue-card { border: 1.5px solid #f0f2f5; border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; }
.issue-card:last-child { margin-bottom: 0; }
.issue-card h4 { font-size: 13.5px; font-weight: 700; margin-bottom: 10px; color: #1a1a2e; }
.issue-card .num-1 { color: #c9323e; } .issue-card .num-2 { color: #e76f51; } .issue-card .num-3 { color: #2d6a4f; }
.issue-row { font-size: 13px; margin-bottom: 6px; display: flex; gap: 8px; }
.issue-row .lbl { flex: 0 0 90px; font-weight: 700; color: #888; font-size: 11px; text-transform: uppercase; padding-top: 2px; }
.issue-row .val { flex: 1; }

.priority-box { background: #1e1e2e; color: #a6e3a1; font-family: 'Consolas', monospace; font-size: 13px; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; line-height: 1.7; }

.proposal-card { border-radius: 10px; padding: 18px 22px; margin-bottom: 16px; border: 1.5px solid #f0f2f5; }
.proposal-card.p0 { border-left: 5px solid #c9323e; }
.proposal-card.p1 { border-left: 5px solid #f4a261; }
.proposal-card h4 { font-size: 14px; font-weight: 700; margin-bottom: 12px; }
.proposal-card .field { font-size: 13px; margin-bottom: 8px; }
.proposal-card .field b { color: #333; }
.p-badge { font-size: 11px; font-weight: 800; padding: 2px 9px; border-radius: 10px; margin-right: 8px; }
.p0-badge { background: #ffe0e3; color: #c9323e; }
.p1-badge { background: #fff3cd; color: #8a6400; }

.reliability-table td:nth-child(3) { color: #1b7a3d; font-size: 12.5px; }

ul.decision-list, ol.decision-list { padding-left: 20px; font-size: 13.5px; }
ul.decision-list li, ol.decision-list li { margin-bottom: 8px; }

.usage-box { background: #1e1e2e; border-radius: 8px; padding: 16px 20px; font-family: monospace; font-size: 13px; color: #a6e3a1; margin: 12px 0; line-height: 1.7; }

.footer-note { text-align: center; font-size: 12px; color: #999; margin-top: 8px; }

@media(max-width:700px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  table { display: block; overflow-x: auto; white-space: nowrap; }
}
"""


# ---------------------------------------------------------------- inline helpers
def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline(t):
    """마크다운 인라인(코드/볼드/이탤릭) -> HTML. 먼저 escape 후 마커 치환."""
    t = esc(t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', t)
    return t


def extract_badges(text):
    """제목/줄에서 배지 토큰(🟢`Basic` 등)을 떼어내고 (남은 텍스트, [(kind,label,emoji)])를 반환."""
    badges = []

    def repl(m):
        badges.append((BADGE_MAP[m.group(1)], m.group(2), m.group(1)))
        return ''

    clean = re.sub(r'(🟢|🟡|🔴)\s*`([^`]*)`', repl, text)
    return clean.strip(), badges


def tags_html(badges):
    return ' '.join(
        f'<span class="tag tag-{kind}">{emoji} {esc(label)}</span>' for kind, label, emoji in badges
    )


# ---------------------------------------------------------------- block parser
def is_block_start(s):
    return bool(
        re.match(r'#{1,6}\s', s) or s.startswith('|') or s.startswith('>')
        or s.startswith('```') or re.match(r'[-*]\s', s) or re.match(r'\d+\.\s', s)
        or re.fullmatch(r'-{3,}', s)
    )


def parse_table(rows):
    def cells(r):
        parts = [c.strip() for c in r.strip().strip('|').split('|')]
        return parts

    header = cells(rows[0])
    body = []
    for r in rows[1:]:
        c = cells(r)
        if all(re.fullmatch(r':?-{2,}:?', x) for x in c if x):  # 구분선 행
            continue
        body.append(c)
    return header, body


def parse_blocks(md):
    lines = md.split('\n')
    blocks, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith('```'):
            code, j = [], i + 1
            while j < n and not lines[j].strip().startswith('```'):
                code.append(lines[j])
                j += 1
            blocks.append({'type': 'code', 'lines': code})
            i = j + 1
            continue
        m = re.match(r'(#{1,6})\s+(.*)', s)
        if m:
            blocks.append({'type': f'h{len(m.group(1))}', 'text': m.group(2).strip()})
            i += 1
            continue
        if re.fullmatch(r'-{3,}', s):
            blocks.append({'type': 'hr'})
            i += 1
            continue
        if s.startswith('|'):
            tbl = []
            while i < n and lines[i].strip().startswith('|'):
                tbl.append(lines[i])
                i += 1
            header, body = parse_table(tbl)
            blocks.append({'type': 'table', 'header': header, 'rows': body})
            continue
        if s.startswith('>'):
            q = []
            while i < n and lines[i].strip().startswith('>'):
                q.append(re.sub(r'^>\s?', '', lines[i].strip()))
                i += 1
            blocks.append({'type': 'quote', 'lines': [x for x in q if x]})
            continue
        if re.match(r'[-*]\s+', s):
            items = []
            while i < n and re.match(r'[-*]\s+', lines[i].strip()):
                items.append(re.sub(r'^[-*]\s+', '', lines[i].strip()))
                i += 1
            blocks.append({'type': 'ul', 'items': items})
            continue
        if re.match(r'\d+\.\s+', s):
            items = []
            while i < n and re.match(r'\d+\.\s+', lines[i].strip()):
                items.append(re.sub(r'^\d+\.\s+', '', lines[i].strip()))
                i += 1
            blocks.append({'type': 'ol', 'items': items})
            continue
        para = [s]
        i += 1
        while i < n and lines[i].strip() and not is_block_start(lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        blocks.append({'type': 'p', 'text': ' '.join(para)})
    return blocks


# ---------------------------------------------------------------- component renderers
def is_footer(text):
    return text.startswith('*') and not text.startswith('**')


def render_kpi(block):
    cards = []
    for idx, row in enumerate(block['rows']):
        if len(row) < 2:
            continue
        label, value = row[0], row[1]
        color = KPI_COLORS[idx % len(KPI_COLORS)]
        cards.append(
            f'<div class="kpi kpi-{color}"><div class="kpi-n">{inline(value)}</div>'
            f'<div class="kpi-l">{inline(label)}</div></div>'
        )
    return '<div class="kpi-row">' + ''.join(cards) + '</div>'


def render_table(block):
    header = block['header']
    header_l = [h.replace('*', '').strip() for h in header]
    is_reliability = header_l[:3] == ['이슈', '내용', '처리']
    has_rank = '순위' in header_l
    roi_col = next((k for k, h in enumerate(header_l) if h.startswith('ROI')), None)

    # 순위 표에서 1위/최하위(가장 큰 순위 숫자) 행 강조 대상 찾기 (채널명 무관, 순위 숫자로만 판단)
    rank_vals = []
    if has_rank:
        for row in block['rows']:
            m = re.fullmatch(r'\d+', row[0].strip()) if row else None
            rank_vals.append(int(row[0]) if m else None)
    worst_rank = max([v for v in rank_vals if v is not None], default=None)

    thead = '<thead><tr>' + ''.join(f'<th>{inline(h)}</th>' for h in header) + '</tr></thead>'
    body_rows = []
    for ridx, row in enumerate(block['rows']):
        first = row[0].replace('*', '').strip() if row else ''
        is_total = first.startswith('합계') or first.startswith('전체')
        rank_here = rank_vals[ridx] if has_rank and ridx < len(rank_vals) else None
        tds = []
        for cidx, cell in enumerate(row):
            classes = []
            core = cell.replace('*', '').strip()
            if re.fullmatch(r'[\d,.\-+%]+', core):
                classes.append('num')
            if has_rank and cidx == 0 and rank_here == 1:
                classes.append('rank1')
            if has_rank and cidx == 0 and rank_here == worst_rank and worst_rank not in (None, 1):
                classes.append('rank-low')
            if roi_col is not None and cidx == roi_col and rank_here == 1:
                classes.append('rank1')
            if roi_col is not None and cidx == roi_col and rank_here == worst_rank and worst_rank not in (None, 1):
                classes.append('rank-low')
            cls = f' class="{" ".join(classes)}"' if classes else ''
            tds.append(f'<td{cls}>{inline(cell)}</td>')
        tr_cls = ' class="total"' if is_total else ''
        body_rows.append(f'<tr{tr_cls}>' + ''.join(tds) + '</tr>')
    tbl_cls = ' class="reliability-table"' if is_reliability else ''
    return f'<table{tbl_cls}>{thead}<tbody>' + ''.join(body_rows) + '</tbody></table>'


def render_fields(ul_block):
    """이슈/기획안 소제목 아래 불릿(**라벨**: 값)을 라벨-값 행으로 렌더."""
    rows = []
    for item in ul_block['items']:
        m = re.match(r'\*\*(.+?)\*\*\s*[:：]\s*(.*)', item)
        if m:
            rows.append(
                f'<div class="issue-row"><span class="lbl">{esc(m.group(1))}</span>'
                f'<span class="val">{inline(m.group(2))}</span></div>'
            )
        else:
            rows.append(f'<div class="issue-row"><span class="val">{inline(item)}</span></div>')
    return ''.join(rows)


def render_issue_card(h3_text, ul_block):
    m = re.match(r'이슈\s*(\d+)\s*[:：]\s*(.*)', h3_text)
    if m:
        num = int(m.group(1))
        title, ncls = m.group(2), f'num-{((num - 1) % 3) + 1}'
        head = f'<h4><span class="{ncls}">이슈 {num}</span> · {inline(title)}</h4>'
    else:
        head = f'<h4>{inline(h3_text)}</h4>'
    fields = render_fields(ul_block) if ul_block else ''
    return f'<div class="issue-card">{head}{fields}</div>'


def render_proposal_card(h3_text, ul_block):
    pm = re.search(r'\[(P\d)\]', h3_text)
    pkey = pm.group(1).lower() if pm else 'p0'
    name = re.sub(r'\s*\[P\d\]\s*', '', h3_text).strip()
    badge = f'<span class="p-badge {pkey}-badge">{pkey.upper()}</span>' if pm else ''
    fields = ''
    for item in (ul_block['items'] if ul_block else []):
        m = re.match(r'\*\*(.+?)\*\*\s*[:：]\s*(.*)', item)
        if m:
            fields += f'<div class="field"><b>{esc(m.group(1))}</b>: {inline(m.group(2))}</div>'
        else:
            fields += f'<div class="field">{inline(item)}</div>'
    return f'<div class="proposal-card {pkey}"><h4>{badge}{inline(name)}</h4>{fields}</div>'


def render_list(block):
    tag = 'ol' if block['type'] == 'ol' else 'ul'
    items = ''.join(f'<li>{inline(it)}</li>' for it in block['items'])
    return f'<{tag} class="decision-list">{items}</{tag}>'


def render_code(block):
    body = '<br>'.join(esc(ln) for ln in block['lines'])
    return f'<div class="usage-box">{body}</div>'


def render_quote(block):
    text = ' '.join(block['lines'])
    cls = 'note-warn' if text.lstrip().startswith('⚠️') else 'note'
    return f'<p class="{cls}">{inline(text)}</p>'


# ---------------------------------------------------------------- section / header
def render_section(h2_block, blocks):
    title_clean, title_badges = extract_badges(h2_block['text'])
    title_html = inline(title_clean) + ((' ' + tags_html(title_badges)) if title_badges else '')
    out = [f'<div class="section"><div class="section-title">{title_html}</div>']

    sub_open = False
    i = 0
    while i < len(blocks):
        b = blocks[i]

        if b['type'] == 'p':
            clean, badges = extract_badges(b['text'])
            if not clean and badges:  # 배지만 있는 줄 -> 소제목(subsection) 시작
                if sub_open:
                    out.append('</div>')
                out.append(f'<div class="subsection"><h3>{tags_html(badges)}</h3>')
                sub_open = True
                i += 1
                continue
            if is_footer(b['text']):  # 푸터는 섹션 밖에서 처리
                i += 1
                continue
            if b['text'].startswith('**한 줄 결론**'):
                out.append(f'<div class="conclusion">{inline(b["text"])}</div>')
            elif b['text'].startswith('**해석**') or b['text'].startswith('**전체 합산'):
                out.append(f'<div class="interp">{inline(b["text"])}</div>')
            else:
                out.append(f'<p style="font-size:13.5px;">{inline(b["text"])}</p>')
            i += 1
            continue

        if b['type'] == 'h3':
            clean, badges = extract_badges(b['text'])
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if re.match(r'이슈\s*\d+', clean):
                ul = nxt if nxt and nxt['type'] == 'ul' else None
                out.append(render_issue_card(clean, ul))
                i += 2 if ul else 1
                continue
            if clean.startswith('기획안'):
                ul = nxt if nxt and nxt['type'] == 'ul' else None
                out.append(render_proposal_card(clean, ul))
                i += 2 if ul else 1
                continue
            h3_html = inline(clean) + ((' ' + tags_html(badges)) if badges else '')
            out.append(f'<h3>{h3_html}</h3>')
            i += 1
            continue

        if b['type'] == 'table':
            header_l = [h.replace('*', '').strip() for h in b['header']]
            if header_l[:2] == ['지표', '값']:
                out.append(render_kpi(b))
            else:
                out.append(render_table(b))
        elif b['type'] in ('ul', 'ol'):
            out.append(render_list(b))
        elif b['type'] == 'code':
            out.append(render_code(b))
        elif b['type'] == 'quote':
            out.append(render_quote(b))
        elif b['type'] == 'h4':
            out.append(f'<h4>{inline(b["text"])}</h4>')
        # hr 등은 섹션 카드가 이미 구분되므로 무시
        i += 1

    if sub_open:
        out.append('</div>')
    out.append('</div>')
    return '\n'.join(out)


def render_header(h1_text, intro_quote, md):
    parts = re.split(r'\s+—\s+|\s*—\s*', h1_text, maxsplit=1)
    title = parts[0].strip()
    meta_chips = []
    if len(parts) > 1:
        for j, piece in enumerate(re.split(r'\s*\|\s*', parts[1])):
            piece = piece.strip()
            if piece:
                meta_chips.append(f'<span>{"👤" if j == 0 else "📅"} {esc(piece)}</span>')
    cleaned = re.search(r'정제\s*후\s*(\d+)\s*행', md)
    original = re.search(r'원본\s*(\d+)\s*행', md)
    if cleaned:
        chip = f'📊 정제 후 {cleaned.group(1)}행'
        if original:
            chip += f' (원본 {original.group(1)}행)'
        meta_chips.append(f'<span>{chip}</span>')

    note_html, legend_html = '', ''
    if intro_quote:
        for ln in intro_quote['lines']:
            if '배지 안내' in ln or re.search(r'🟢.*🟡.*🔴', ln):
                legend_html = f'<div class="legend">{inline(ln)}</div>'
            else:
                note_html += f'<div class="header-note">{inline(ln)}</div>'

    meta = f'<div class="header-meta">{"".join(meta_chips)}</div>' if meta_chips else ''
    return (
        '<div class="header">'
        f'<h1>{esc(title)}</h1>{meta}{note_html}{legend_html}</div>'
    )


def render_footer(md):
    footers = []
    for b in parse_blocks(md):
        if b['type'] == 'p' and is_footer(b['text']):
            html = inline(b['text']).replace('</i> <i>', '</i><br><i>')
            footers.append(html)
    if not footers:
        return ''
    return f'<p class="footer-note">{"<br>".join(footers)}</p>'


def md_to_html(md):
    blocks = parse_blocks(md)
    h1_text = next((b['text'] for b in blocks if b['type'] == 'h1'), '마케팅 성과 인사이트 리포트')

    intro_quote, sections, cur = None, [], None
    for b in blocks:
        if b['type'] == 'h1':
            continue
        if b['type'] == 'h2':
            cur = (b, [])
            sections.append(cur)
        elif cur is None:
            if b['type'] == 'quote' and intro_quote is None:
                intro_quote = b
        else:
            cur[1].append(b)

    body = [render_header(h1_text, intro_quote, md)]
    for h2_block, sec_blocks in sections:
        body.append(render_section(h2_block, sec_blocks))
    footer = render_footer(md)
    if footer:
        body.append(footer)

    return (
        '<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>{esc(h1_text)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n'
        '<div class="container">\n\n' + '\n\n'.join(body) + '\n\n</div>\n</body>\n</html>\n'
    )


def main():
    md_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MD
    html_out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HTML

    md = Path(md_path).read_text(encoding='utf-8')
    html = md_to_html(md)
    Path(html_out).parent.mkdir(parents=True, exist_ok=True)
    Path(html_out).write_text(html, encoding='utf-8')

    sections = html.count('<div class="section">')
    print(f"[render_html] {md_path} -> {html_out}")
    print(f"[render_html] 섹션 {sections}개, {len(html):,}바이트 생성 완료")


if __name__ == '__main__':
    main()
