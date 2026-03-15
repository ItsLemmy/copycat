#!/usr/bin/env python3
"""
Recolorize Copycat icon theme folder icons.

Takes a source Copycat theme directory and produces a recolored copy
of all places/folder SVGs. Supports both the reserved/folders (emblemed)
and places/scalable (color variants) directories.

The script works by replacing the known base colors in SVGs with your
target palette. Each folder SVG uses up to 5 color roles:

  - back:     solid fill for the back panel
  - grad_lo:  gradient stop 0 (darker, bottom)
  - grad_hi:  gradient stop 1 (lighter, top)
  - glyph_lo: glyph/emblem gradient stop 0 (darker)
  - glyph_hi: glyph/emblem gradient stop 1 (lighter)

Usage:
    ./copycat-recolor.py --help
    ./copycat-recolor.py --list-presets
    ./copycat-recolor.py --preset dracula src/ out/
    ./copycat-recolor.py --accent '#eb6f92' src/ out/
    ./copycat-recolor.py --noctalia src/ out/ --install
"""

import argparse
import colorsys
import json
import os
import re
import shutil
import sys

# --- Default Copycat blue base colors (source colors to replace) ---

EMBLEM_COLORS = {
    "back":     "#0083d5",
    "grad_lo":  "#1075f6",
    "grad_hi":  "#12c5ff",
    "glyph_lo": "#0b4f94",
    "glyph_hi": "#126c98",
}

VARIANT_COLORS = {
    "default": {
        "back":    "#0083d5",
        "grad_lo": "#1075f6",
        "grad_hi": "#12c5ff",
    },
    "blue": {
        "back":    "rgb(1,41,180)",
        "grad_lo": "rgb(0,7,140)",
        "grad_hi": "rgb(2,105,255)",
    },
    "red": {
        "back":    "rgb(133,20,3)",
        "grad_lo": "rgb(119,17,0)",
        "grad_hi": "rgb(233,42,20)",
    },
    "green": {
        "back":    "rgb(13,138,56)",
        "grad_lo": "rgb(0,124,48)",
        "grad_hi": "rgb(82,216,99)",
    },
    "grey": {
        "back":    "rgb(84,84,84)",
        "grad_lo": "rgb(76,76,76)",
        "grad_hi": "rgb(137,137,137)",
    },
    "black": {
        "back":    "#1b1b1b",
        "grad_lo": "#0c0c0c",
        "grad_hi": "#454545",
    },
    "cyan": {
        "back":    "rgb(2,160,172)",
        "grad_lo": "rgb(0,130,140)",
        "grad_hi": "rgb(0,210,220)",
    },
    "orange": {
        "back":    "rgb(172,63,6)",
        "grad_lo": "rgb(155,48,0)",
        "grad_hi": "rgb(255,135,32)",
    },
    "brown": {
        "back":    "rgb(123,86,48)",
        "grad_lo": "rgb(86,52,32)",
        "grad_hi": "rgb(165,125,66)",
    },
    "magenta": {
        "back":    "rgb(128,2,67)",
        "grad_lo": "rgb(119,0,62)",
        "grad_hi": "rgb(233,20,121)",
    },
    "violet": {
        "back":    "rgb(86,33,102)",
        "grad_lo": "rgb(102,53,115)",
        "grad_hi": "rgb(149,0,255)",
    },
    "yellow": {
        "back":    "rgb(166,144,0)",
        "grad_lo": "rgb(157,137,0)",
        "grad_hi": "rgb(255,211,0)",
    },
}

# --- Color presets ---

PRESETS = {
    "dracula": {
        "desc": "Dracula theme (dark purple/grey)",
        "back":     "#282a36",
        "grad_lo":  "#44475a",
        "grad_hi":  "#6272a4",
        "glyph_lo": "#1a1c25",
        "glyph_hi": "#2d3045",
    },
    "catppuccin-mocha": {
        "desc": "Catppuccin Mocha (dark lavender)",
        "back":     "#1e1e2e",
        "grad_lo":  "#313244",
        "grad_hi":  "#585b70",
        "glyph_lo": "#14141f",
        "glyph_hi": "#24243a",
    },
    "nord": {
        "desc": "Nord (arctic blue-grey)",
        "back":     "#2e3440",
        "grad_lo":  "#3b4252",
        "grad_hi":  "#4c566a",
        "glyph_lo": "#232831",
        "glyph_hi": "#333a47",
    },
    "gruvbox": {
        "desc": "Gruvbox Dark (warm brown)",
        "back":     "#282828",
        "grad_lo":  "#3c3836",
        "grad_hi":  "#665c54",
        "glyph_lo": "#1d2021",
        "glyph_hi": "#32302f",
    },
    "solarized-dark": {
        "desc": "Solarized Dark (dark teal)",
        "back":     "#002b36",
        "grad_lo":  "#073642",
        "grad_hi":  "#586e75",
        "glyph_lo": "#001f27",
        "glyph_hi": "#04313b",
    },
    "tokyo-night": {
        "desc": "Tokyo Night (dark indigo)",
        "back":     "#1a1b26",
        "grad_lo":  "#24283b",
        "grad_hi":  "#414868",
        "glyph_lo": "#12131c",
        "glyph_hi": "#1e2030",
    },
    "rose-pine": {
        "desc": "Rose Pine (muted purple)",
        "back":     "#26233a",
        "grad_lo":  "#393552",
        "grad_hi":  "#6e6a86",
        "glyph_lo": "#1f1d2e",
        "glyph_hi": "#2a2740",
    },
    "neutral-grey": {
        "desc": "True neutral grey (no color tint)",
        "back":     "#3a3a3a",
        "grad_lo":  "#4a4a4a",
        "grad_hi":  "#707070",
        "glyph_lo": "#2a2a2a",
        "glyph_hi": "#3d3d3d",
    },
}

NOCTALIA_COLORS_PATH = os.path.expanduser("~/.config/noctalia/colors.json")


# --- Color utilities ---

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def parse_css_color(c):
    c = c.strip()
    if c.startswith("#"):
        return hex_to_rgb(c)
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", c)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    raise ValueError(f"Cannot parse color: {c}")


def color_to_hex_and_rgb(c):
    r, g, b = parse_css_color(c)
    return rgb_to_hex(r, g, b), f"rgb({r},{g},{b})"


def adjust_tone(hex_color, lightness):
    """Adjust a hex color's lightness (0.0-1.0) while preserving hue and saturation."""
    r, g, b = hex_to_rgb(hex_color)
    h, _, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(h, lightness, s)
    return rgb_to_hex(int(r2 * 255), int(g2 * 255), int(b2 * 255))


def derive_from_accent(accent_hex):
    """Derive 5 folder color roles from a single accent color."""
    r, g, b = hex_to_rgb(accent_hex)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    # Desaturate and darken for folder body tones
    s_folder = min(s, 0.35)
    def make(lightness, sat=s_folder):
        r2, g2, b2 = colorsys.hls_to_rgb(h, lightness, sat)
        return rgb_to_hex(int(r2 * 255), int(g2 * 255), int(b2 * 255))
    return {
        "back":     make(0.18),
        "grad_lo":  make(0.25),
        "grad_hi":  make(0.42),
        "glyph_lo": make(0.12),
        "glyph_hi": make(0.20),
    }


def tint_color(base_hex, accent_hex, amount):
    """Blend accent hue/saturation into a base color.

    amount=0.0 keeps the base as-is, amount=1.0 fully replaces with accent's hue.
    The base's lightness is preserved; saturation is boosted toward the accent.
    """
    br, bg, bb = hex_to_rgb(base_hex)
    ar, ag, ab = hex_to_rgb(accent_hex)
    bh, bl, bs = colorsys.rgb_to_hls(br / 255, bg / 255, bb / 255)
    ah, al, a_s = colorsys.rgb_to_hls(ar / 255, ag / 255, ab / 255)
    # Use accent hue, blend saturation, keep base lightness
    new_h = ah
    new_s = bs + (a_s - bs) * amount
    # Ensure minimum saturation so the tint is visible
    new_s = max(new_s, a_s * amount * 0.5)
    r2, g2, b2 = colorsys.hls_to_rgb(new_h, bl, min(new_s, 1.0))
    return rgb_to_hex(int(r2 * 255), int(g2 * 255), int(b2 * 255))


def derive_from_noctalia(colors_path=None):
    """Read noctalia colors.json and derive folder colors using the accent."""
    path = colors_path or NOCTALIA_COLORS_PATH
    if not os.path.exists(path):
        print(f"Error: noctalia colors not found at '{path}'", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        palette = json.load(f)

    primary = palette.get("mPrimary", "#6272a4")
    surface = palette.get("mSurface", "#191724")
    surface_var = palette.get("mSurfaceVariant", "#26233a")
    outline = palette.get("mOutline", "#403d52")
    shadow = palette.get("mShadow", "#191724")
    on_surface_var = palette.get("mOnSurfaceVariant", "#908caa")

    # Tint the neutral surface colors with the primary accent hue
    # Higher amount = more accent color visible
    tint = 0.7

    sr, sg, sb = hex_to_rgb(shadow)
    vr, vg, vb = hex_to_rgb(surface)
    glyph_hi_base = rgb_to_hex((sr + vr) // 2, (sg + vg) // 2, (sb + vb) // 2)

    return {
        "back":     tint_color(surface_var, primary, tint),
        "grad_lo":  tint_color(outline, primary, tint),
        "grad_hi":  tint_color(on_surface_var, primary, tint),
        "glyph_lo": tint_color(shadow, primary, tint * 0.5),
        "glyph_hi": tint_color(glyph_hi_base, primary, tint * 0.5),
    }


# --- SVG recoloring ---

def detect_variant_colors(svg_content):
    for name, colors in VARIANT_COLORS.items():
        if colors["back"] in svg_content:
            return name, colors
    return None, None


def soften_gradients(target, amount=0.5):
    """Blend gradient high stops toward low stops to reduce gradient contrast.

    amount=0.0 keeps original spread, amount=1.0 collapses to flat.
    """
    target = dict(target)
    for lo, hi in (("grad_lo", "grad_hi"), ("glyph_lo", "glyph_hi")):
        r1, g1, b1 = hex_to_rgb(target[lo])
        r2, g2, b2 = hex_to_rgb(target[hi])
        r = int(r2 + (r1 - r2) * amount)
        g = int(g2 + (g1 - g2) * amount)
        b = int(b2 + (b1 - b2) * amount)
        target[hi] = rgb_to_hex(r, g, b)
    return target


def flatten_gradients(content, target):
    content = content.replace("url(#front-gradient)", target["grad_lo"])
    content = content.replace("url(#glyph-gradient)", target["glyph_lo"])
    return content


def recolor_svg(content, target, is_emblemed=False, flat=False):
    if is_emblemed:
        replacements = [
            (EMBLEM_COLORS["back"],     target["back"]),
            (EMBLEM_COLORS["grad_lo"],  target["grad_lo"]),
            (EMBLEM_COLORS["grad_hi"],  target["grad_hi"]),
            (EMBLEM_COLORS["glyph_lo"], target["glyph_lo"]),
            (EMBLEM_COLORS["glyph_hi"], target["glyph_hi"]),
        ]
        for old, new in replacements:
            content = content.replace(old, new)
    else:
        variant_name, variant_colors = detect_variant_colors(content)
        if variant_colors:
            for role in ("back", "grad_lo", "grad_hi"):
                old = variant_colors[role]
                new = target[role]
                old_hex, old_rgb = color_to_hex_and_rgb(old)
                new_hex, _ = color_to_hex_and_rgb(new)
                content = content.replace(old, new_hex)
                if old_hex != old:
                    content = content.replace(old_hex, new_hex)
                if old_rgb != old:
                    content = content.replace(old_rgb, new_hex)
            for role in ("glyph_lo", "glyph_hi"):
                old = EMBLEM_COLORS[role]
                new = target[role]
                content = content.replace(old, new)
    if flat:
        content = flatten_gradients(content, target)
    return content


# --- Theme processing ---

def process_theme(src_dir, out_dir, target_colors, theme_name=None, flat=False):
    if not os.path.isdir(src_dir):
        print(f"Error: source directory '{src_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(src_dir, out_dir, symlinks=True)

    recolored = 0

    for dirpath, dirnames, filenames in os.walk(out_dir):
        for fname in filenames:
            if not fname.endswith(".svg"):
                continue
            fpath = os.path.join(dirpath, fname)
            if os.path.islink(fpath):
                continue
            with open(fpath, "r") as f:
                content = f.read()

            has_emblem = any(c in content for c in EMBLEM_COLORS.values())
            has_variant = any(
                colors["back"] in content
                for colors in VARIANT_COLORS.values()
            )
            if not has_emblem and not has_variant:
                continue

            is_emblemed = "glyph-gradient" in content or EMBLEM_COLORS["glyph_lo"] in content
            new_content = recolor_svg(content, target_colors, is_emblemed=is_emblemed, flat=flat)
            if new_content != content:
                with open(fpath, "w") as f:
                    f.write(new_content)
                recolored += 1

    if theme_name:
        index_path = os.path.join(out_dir, "index.theme")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                content = f.read()
            content = re.sub(r"^Name=.*$", f"Name={theme_name}", content, flags=re.MULTILINE)
            content = re.sub(r"^Comment=.*$", f"Comment={theme_name} - Recolored Copycat", content, flags=re.MULTILINE)
            with open(index_path, "w") as f:
                f.write(content)

    print(f"Recolored {recolored} SVG files in '{out_dir}'")


def list_presets():
    print("Available presets:\n")
    for name, p in sorted(PRESETS.items()):
        colors = f"  back={p['back']}  grad_lo={p['grad_lo']}  grad_hi={p['grad_hi']}"
        print(f"  {name:20s} {p['desc']}")
        print(f"  {' ':20s} {colors}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Recolorize Copycat icon theme folder icons.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("src", nargs="?", help="Source Copycat theme directory")
    parser.add_argument("out", nargs="?", help="Output directory for the recolored theme")
    parser.add_argument("--preset", "-p", choices=list(PRESETS.keys()),
                        help="Use a color preset")
    parser.add_argument("--list-presets", action="store_true",
                        help="List available color presets")
    parser.add_argument("--accent", "-a",
                        help="Single accent color (hex) — derives all 5 roles automatically")
    parser.add_argument("--noctalia", action="store_true",
                        help="Read colors from ~/.config/noctalia/colors.json")
    parser.add_argument("--noctalia-path",
                        help="Custom path to noctalia colors.json")
    parser.add_argument("--name", "-n", help="Custom theme name for index.theme")
    parser.add_argument("--back", help="Back panel color (hex)")
    parser.add_argument("--grad-lo", help="Front gradient dark stop (hex)")
    parser.add_argument("--grad-hi", help="Front gradient light stop (hex)")
    parser.add_argument("--glyph-lo", help="Glyph/emblem gradient dark stop (hex)")
    parser.add_argument("--glyph-hi", help="Glyph/emblem gradient light stop (hex)")
    parser.add_argument("--flat", action="store_true",
                        help="Remove gradients — use flat solid colors instead")
    parser.add_argument("--install", "-i", action="store_true",
                        help="Install to ~/.local/share/icons/ and update icon cache")
    parser.add_argument("--apply", action="store_true",
                        help="Set as the active icon theme after installing (implies --install)")

    args = parser.parse_args()

    if args.list_presets:
        list_presets()
        return

    if not args.src or not args.out:
        parser.error("src and out arguments are required (unless using --list-presets)")

    if args.apply:
        args.install = True

    # Build target colors from the chosen source
    target = None
    if args.noctalia:
        target = derive_from_noctalia(args.noctalia_path)
    elif args.accent:
        target = derive_from_accent(args.accent)
    elif args.preset:
        target = dict(PRESETS[args.preset])
        target.pop("desc", None)
    elif args.back:
        target = {
            "back":     args.back,
            "grad_lo":  args.grad_lo or args.back,
            "grad_hi":  args.grad_hi or args.back,
            "glyph_lo": args.glyph_lo or args.back,
            "glyph_hi": args.glyph_hi or args.back,
        }
    else:
        parser.error("Specify --preset, --accent, --noctalia, or at least --back")

    # Allow per-role overrides on top of any source
    if args.back:     target["back"]     = args.back
    if args.grad_lo:  target["grad_lo"]  = args.grad_lo
    if args.grad_hi:  target["grad_hi"]  = args.grad_hi
    if args.glyph_lo: target["glyph_lo"] = args.glyph_lo
    if args.glyph_hi: target["glyph_hi"] = args.glyph_hi

    # Soften gradients unless using flat mode
    if not args.flat:
        target = soften_gradients(target)

    # Determine theme name
    if args.name:
        theme_name = args.name
    elif args.noctalia:
        theme_name = "Copycat-noctalia"
    elif args.accent:
        theme_name = f"Copycat-accent"
    elif args.preset:
        theme_name = f"Copycat-{args.preset}"
    else:
        theme_name = "Copycat-custom"

    print(f"Colors: back={target['back']} grad_lo={target['grad_lo']} "
          f"grad_hi={target['grad_hi']} glyph_lo={target['glyph_lo']} "
          f"glyph_hi={target['glyph_hi']}")

    process_theme(args.src, args.out, target, theme_name, flat=args.flat)

    if args.install:
        install_dir = os.path.expanduser(f"~/.local/share/icons/{theme_name}")
        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
        shutil.copytree(args.out, install_dir, symlinks=True)
        os.system(f"gtk-update-icon-cache -f '{install_dir}' 2>/dev/null")
        print(f"Installed to {install_dir}")

    if args.apply:
        os.system(f"gsettings set org.gnome.desktop.interface icon-theme '{theme_name}'")
        print(f"Applied icon theme '{theme_name}'")


if __name__ == "__main__":
    main()
