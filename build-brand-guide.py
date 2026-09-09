#!/usr/bin/env python3
"""릴라이브 브랜드센터 빌드.

rillive-brand-guide.template.html 의 플레이스홀더를 채운다.
  __FONTFACE__   → 페이지에 쓰인 글자만 서브셋한 Pretendard JP (woff2 data URI)
  __LOGO_JSON__  → 카드별 다운로드용 SVG 문자열 dict
  __ZIP_B64__    → 로고 패키지 zip (base64, JS에서 blob으로 디코드)

부산물: assets/logo-package/ (svg/, png/, README.txt) + rillive-logo-package.zip
PNG는 Chrome 헤드리스로 투명 배경 렌더. 본문을 고치면 반드시 재빌드(폰트 서브셋).
"""
import base64
import datetime
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "rillive-brand-guide.template.html"
OUT = ROOT / "rillive-brand-guide.html"
FONT_DIR = pathlib.Path.home() / "Library" / "Fonts"
PKG_DIR = ROOT / "assets" / "logo-package"
ZIP_PATH = ROOT / "rillive-logo-package.zip"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

WEIGHTS = [
    ("PretendardJP-Regular.otf", 400),
    ("PretendardJP-Medium.otf", 500),
    ("PretendardJP-SemiBold.otf", 600),
    ("PretendardJP-Bold.otf", 700),
]

# ── 로고 아트워크 (피그마 Logo/Logo 정본에서 export한 좌표) ──────────
GRAD = ('<linearGradient id="g" x1="0" y1="7.63" x2="53.04" y2="23.13" '
        'gradientUnits="userSpaceOnUse"><stop stop-color="#507DFF"/>'
        '<stop offset=".5" stop-color="#6A5CFF"/>'
        '<stop offset="1" stop-color="#7D55FF"/></linearGradient>')
FACE = ("M33.0502 11.7781C38.4615 11.7781 42.8507 16.2658 42.851 21.7967C42.851 21.7967 43.7745 36.4636 24.0004 36.4637"
        "C4.2261 36.4637 5.14981 21.7967 5.14981 21.7967C5.15006 16.2611 9.5384 11.7782 14.9496 11.7781"
        "C16.4036 11.7781 17.7831 12.1044 19.0219 12.6834L19.2768 12.8026C19.2768 12.8026 24.2877 15.1428 28.7328 12.8026"
        "C30.0337 12.1447 31.4995 11.7782 33.0502 11.7781ZM17.4857 21.2459C16.4666 21.2461 15.6405 22.0725 15.64 23.0916"
        "C15.64 24.1111 16.4663 24.9381 17.4857 24.9383C18.5053 24.9382 19.3324 24.1112 19.3324 23.0916"
        "C19.332 22.0724 18.505 21.246 17.4857 21.2459ZM31.2006 21.2459C30.1813 21.2459 29.3544 22.0724 29.3539 23.0916"
        "C29.3539 24.1112 30.181 24.9383 31.2006 24.9383C32.22 24.9381 33.0463 24.1111 33.0463 23.0916"
        "C33.0458 22.0725 32.2197 21.2461 31.2006 21.2459Z")
WM_PATHS = [
    "M199.564 25.068C199.467 24.6796 199.289 24.2265 199.03 23.7087C198.803 23.1584 198.447 22.6406 197.962 22.1551C197.476 21.6696 196.861 21.265 196.117 20.9414C195.372 20.6177 194.482 20.4559 193.447 20.4559C192.411 20.4559 191.521 20.6177 190.776 20.9414C190.032 21.265 189.417 21.6696 188.932 22.1551C188.446 22.6406 188.074 23.1584 187.815 23.7087C187.588 24.2265 187.427 24.6796 187.329 25.068H199.564ZM206.7 33.0786C206.053 34.5998 205.26 35.943 204.322 37.1081C203.383 38.2409 202.347 39.1957 201.214 39.9725C198.949 41.5908 196.392 42.3999 193.544 42.3999C191.602 42.3999 189.773 42.0439 188.058 41.3319C186.342 40.5875 184.821 39.5679 183.494 38.2733C182.199 36.9787 181.164 35.4736 180.387 33.7583C179.643 32.0105 179.27 30.1333 179.27 28.1266C179.27 26.2494 179.61 24.4369 180.29 22.6891C181.002 20.9414 181.989 19.404 183.251 18.077C184.514 16.75 186.002 15.6819 187.718 14.8728C189.466 14.0636 191.359 13.6591 193.398 13.6591C195.437 13.6591 197.331 14.0474 199.078 14.8242C200.826 15.5686 202.331 16.6044 203.593 17.9313C204.856 19.2584 205.843 20.8281 206.555 22.6406C207.267 24.4207 207.623 26.3303 207.623 28.3693C207.623 28.9196 207.607 29.3403 207.574 29.6316C207.542 29.8905 207.493 30.1818 207.429 30.5055H187.232C187.491 32.1238 188.203 33.386 189.369 34.2923C190.566 35.1662 191.958 35.6031 193.544 35.6031C194.774 35.6031 195.761 35.3604 196.505 34.8749C197.25 34.3894 197.897 33.7906 198.447 33.0786H206.7Z",
    "M168.237 41.5261H160.518L150.856 14.5815H159.207L164.353 31.3794H164.45L169.596 14.5815H177.947L168.237 41.5261Z",
    "M147.112 11.7171H139.053V5.59998H147.112V11.7171ZM147.112 41.5261H139.053V14.5815H147.112V41.5261Z",
    "M125.161 5.59998H133.22V41.5261H125.161V5.59998Z",
    "M111.27 5.59998H119.329V41.5261H111.27V5.59998Z",
    "M105.437 11.7171H97.3783V5.59998H105.437V11.7171ZM105.437 41.5261H97.3783V14.5815H105.437V41.5261Z",
    "M74.7877 23.6601H78.0405C79.3998 23.6601 80.4679 23.4821 81.2447 23.1261C82.0538 22.7377 82.6526 22.2846 83.041 21.7667C83.4617 21.2165 83.7369 20.6501 83.8663 20.0675C83.9958 19.4849 84.0605 18.9671 84.0605 18.514C84.0605 16.8633 83.5103 15.6496 82.4099 14.8728C81.3418 14.0636 79.9177 13.6591 78.1376 13.6591H74.7877V23.6601ZM66.0004 5.59998H77.3608C78.9467 5.59998 80.3061 5.64852 81.4389 5.74562C82.5717 5.84272 83.5588 6.00455 84.4004 6.23111C85.2419 6.42531 85.9701 6.68423 86.5851 7.00789C87.2324 7.33155 87.8473 7.71994 88.4299 8.17306C89.9187 9.33823 91.0192 10.8109 91.7312 12.591C92.4756 14.3388 92.8478 16.1351 92.8478 17.9799C92.8478 19.0156 92.7022 20.1322 92.4109 21.3298C92.1196 22.5273 91.6179 23.6763 90.9059 24.7767C90.2262 25.8448 89.3038 26.7996 88.1386 27.6411C87.0058 28.4503 85.5979 29.0005 83.9149 29.2918L93.6732 41.5261H83.1866L74.8848 29.9229H74.7877V41.5261H66.0004V5.59998Z",
]

# 변형별 색: (rect_fill, face_fill, wm_fill)  — wm_fill=None이면 심볼 단독
VARIANTS = {
    "color":         ("url(#g)", "#FFFFFF", "#1A1A1A"),
    "color-on-dark": ("url(#g)", "#FFFFFF", "#FFFFFF"),
    "black":         ("#1A1A1A", "#FFFFFF", "#1A1A1A"),
    "white":         ("#FFFFFF", "#1A1A1A", "#FFFFFF"),
}


def svg_mark(rect_fill, face_fill, x=0.0, y=0.0):
    g = f'<g transform="translate({x:g},{y:g})">' if (x or y) else "<g>"
    return (f'{g}<rect width="48" height="48" rx="10.5763" fill="{rect_fill}"/>'
            f'<path d="{FACE}" fill="{face_fill}"/></g>')


def svg_wm(fill, tx, ty):
    paths = "".join(f'<path d="{p}"/>' for p in WM_PATHS)
    return f'<g transform="translate({tx:g},{ty:g})" fill="{fill}">{paths}</g>'


def build_svg(kind, variant, w=None, h=None):
    rect_fill, face_fill, wm_fill = VARIANTS[variant]
    if kind == "symbol":
        vb, body = "0 0 48 48", svg_mark(rect_fill, face_fill)
    elif kind == "horizontal":
        # 마크 0..48, 워드마크 원좌표 66..207.7 (시그니처 정본 간격)
        vb = "0 0 207.7 48"
        body = svg_mark(rect_fill, face_fill) + svg_wm(wm_fill, 0, 0)
    else:  # vertical: 마크 중앙 상단 + 워드마크 아래 (y 64..100)
        vb = "0 0 141.7 100"
        body = svg_mark(rect_fill, face_fill, x=(141.7 - 48) / 2) + svg_wm(wm_fill, -66, 58.4)
    size = f' width="{w}" height="{h}"' if w else ""
    grad = f"<defs>{GRAD}</defs>" if "url(#g)" in rect_fill else ""
    return (f'<svg{size} viewBox="{vb}" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f"{grad}{body}</svg>")


def render_png(svg_text, out_path, w, h):
    tmp = out_path.with_suffix(".tmp.svg")
    tmp.write_text(svg_text)
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--screenshot={out_path}", f"--window-size={w},{h}",
         "--default-background-color=00000000", f"file://{tmp}"],
        check=True, capture_output=True)
    tmp.unlink()
    # PNG 컬러타입 검사: IHDR color type(byte 25) == 6 → RGBA(투명)
    ct = out_path.read_bytes()[25]
    return ct == 6


def build_logo_package():
    svg_dir = PKG_DIR / "svg"
    png_dir = PKG_DIR / "png"
    if PKG_DIR.exists():
        shutil.rmtree(PKG_DIR)
    svg_dir.mkdir(parents=True)
    png_dir.mkdir(parents=True)

    logo_json = {}
    files = []
    print("로고 패키지:")
    for kind in ("horizontal", "vertical", "symbol"):
        variants = ("color", "black", "white") if kind == "symbol" else VARIANTS.keys()
        for variant in variants:
            name = f"rillive-{kind}-{variant}"
            svg = build_svg(kind, variant)
            (svg_dir / f"{name}.svg").write_text(svg)
            files.append(f"svg/{name}.svg")
            logo_json[f"{kind}-{variant}"] = svg
            if kind == "horizontal":
                w, h = 1662, 384
            elif kind == "vertical":
                w, h = 1134, 800
            else:
                w, h = 1024, 1024
            png_path = png_dir / f"{name}.png"
            alpha = render_png(build_svg(kind, variant, w, h), png_path, w, h)
            files.append(f"png/{name}.png")
            kb = png_path.stat().st_size / 1024
            print(f"  {name:32s} svg + png {w}×{h} ({kb:5.1f} KB{'‧alpha' if alpha else '‧NO ALPHA!'})")
            if not alpha:
                sys.exit("PNG에 알파 채널이 없음 — Chrome 렌더 설정 확인 필요")

    readme = """Rillive 로고 패키지 v2.0
========================

svg/  벡터 원본 (권장 — 크기 제약 없음)
png/  투명 배경 래스터 (horizontal 1662px · vertical 1134px · symbol 1024px)

파일명 규칙
  rillive-{형태}-{테마}
  형태: horizontal(가로형) · vertical(세로형) · symbol(심볼 단독)
  테마: color(밝은 배경) · color-on-dark(어두운 배경) · black/white(단색)

사용 규칙 요약
  - 밝은 배경 → color, 어두운 배경 → color-on-dark 또는 white
  - 보호 여백: 사방 심볼 높이의 1/2 이상
  - 최소 크기: 락업 96px · 심볼 24px
  - 비율/회전/색 변형, 효과 추가 금지
  자세한 규정: 릴라이브 브랜드센터 문서를 따릅니다.

(c) Rematch. Rillive Design System이 정본입니다.
"""
    (PKG_DIR / "README.txt").write_text(readme)
    files.append("README.txt")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            z.write(PKG_DIR / rel, f"rillive-logo-package/{rel}")
    kb = ZIP_PATH.stat().st_size / 1024
    print(f"  {'zip':32s} {kb:.0f} KB → {ZIP_PATH.name}")
    return logo_json, ZIP_PATH.read_bytes()


BASE_URL = "https://rillive-brandcenter.pages.dev"  # 배포 도메인 (OG 절대경로용)


def build_head_meta():
    """파비콘(심볼 data URI) + OG/Twitter 프리뷰 메타. 호스팅 시 링크 미리보기용."""
    fav = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'>"
           "<defs><linearGradient id='g' x1='0' y1='7.63' x2='53.04' y2='23.13' "
           "gradientUnits='userSpaceOnUse'><stop stop-color='#507DFF'/>"
           "<stop offset='.5' stop-color='#6A5CFF'/><stop offset='1' stop-color='#7D55FF'/>"
           "</linearGradient></defs><rect width='48' height='48' rx='10.5763' fill='url(#g)'/>"
           f"<path d='{FACE}' fill='#fff'/></svg>")
    fav_uri = "data:image/svg+xml;base64," + base64.b64encode(fav.encode()).decode()
    desc = "릴라이브 브랜드 로고·컬러·타이포·에셋 가이드라인과 다운로드 리소스"
    return "\n".join([
        f'<link rel="icon" type="image/svg+xml" href="{fav_uri}">',
        '<meta name="theme-color" content="#0D0C11">',
        f'<meta name="description" content="{desc}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:title" content="릴라이브 브랜드센터">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{BASE_URL}/">',
        f'<meta property="og:image" content="{BASE_URL}/og-image.png">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="릴라이브 브랜드센터">',
        f'<meta name="twitter:description" content="{desc}">',
        f'<meta name="twitter:image" content="{BASE_URL}/og-image.png">',
    ])


def build_og_image():
    """1200×630 OG 프리뷰 — 브랜드 그라데이션 바탕 + 흰 워드마크 락업."""
    svg = (
        '<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{GRAD.replace(chr(34)+"g"+chr(34), chr(34)+"bg"+chr(34))}</defs>'
        '<rect width="1200" height="630" fill="#F1F0F8"/>'
        # 락업: 심볼(0..48) + 워드마크(66..207.7), 스케일 2.4배, 중앙 배치
        '<g transform="translate(345,255) scale(2.4)">'
        f'<defs>{GRAD}</defs>'
        + svg_mark("url(#g)", "#FFFFFF")
        + svg_wm("#1A1A1A", 0, 0)
        + '</g>'
        '<text x="600" y="470" text-anchor="middle" font-family="sans-serif" '
        'font-size="30" font-weight="600" fill="#55585F">Brand Center</text>'
        '</svg>'
    )
    out = ROOT / "og-image.png"
    render_png(svg, out, 1200, 630)
    print(f"  {'og-image.png':32s} 1200×630 ({out.stat().st_size/1024:.0f} KB)")
    return out


def visible_text(html: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    s = re.sub(r"<svg\b[^>]*>.*?</svg>", " ", s, flags=re.S | re.I)
    contents = re.findall(r'content:\s*"([^"]*)"', s)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&lsquo;|&rsquo;", "'", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&nbsp;", " ", s)
    return s + " " + " ".join(contents)


def subset_font(path: pathlib.Path, chars: set) -> bytes:
    font = TTFont(str(path))
    opts = Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    font.close()
    return buf.getvalue()


def build_fontface(chars: set) -> str:
    blocks = []
    total = 0
    for filename, weight in WEIGHTS:
        src = FONT_DIR / filename
        if not src.exists():
            sys.exit(f"폰트 없음: {src}")
        data = subset_font(src, chars)
        total += len(data)
        b64 = base64.b64encode(data).decode()
        blocks.append(
            "@font-face{font-family:'Pretendard JP';font-style:normal;"
            f"font-weight:{weight};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
        print(f"  {filename:28s} weight {weight}  {len(data)/1024:6.1f} KB")
    print(f"  {'합계':28s}            {total/1024:6.1f} KB")
    return "\n".join(blocks)


def main():
    html = SRC.read_text()

    logo_json, zip_bytes = build_logo_package()
    print("메타/프리뷰:")
    build_og_image()
    # 최종 업데이트일 — 문서가 최신인지 알 수 있게 빌드 시각을 박는다
    today = datetime.date.today()
    html = html.replace("__BUILD_DATE__", f"{today.year}. {today.month}. {today.day}.")
    html = html.replace("__HEAD_META__", build_head_meta())
    html = html.replace("__LOGO_JSON__", json.dumps(logo_json, ensure_ascii=False))
    # zip은 data: URL이 아니라 base64 문자열로 심는다 — data: 다운로드는 Chrome이 차단.
    # JS가 base64→Uint8Array→Blob→objectURL로 내려준다.
    zip_b64 = base64.b64encode(zip_bytes).decode()
    print(f"  zip base64: {len(zip_b64)/1024:.0f} KB")
    html = html.replace("__ZIP_B64__", zip_b64)

    glyphs = set(visible_text(html))
    glyphs |= set("0123456789abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ.,·—–-()%#/×°&'’‘“”:;!?→⬇◐ ")
    print(f"\n폰트 서브셋 — 고유 글자 {len(glyphs)}자:")
    html = html.replace("__FONTFACE__", build_fontface(glyphs))

    OUT.write_text(html)
    print(f"\n완료 → {OUT}  ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
