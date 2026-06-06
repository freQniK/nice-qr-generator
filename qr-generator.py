#!/usr/bin/env python3
"""
Stylized QR Code Generator with Circular Dots, Rounded Finder Patterns,
and Smooth Logo Blending - Golden Yellow on Black.

Requirements:
    pip install qrcode[pil] Pillow numpy

Usage:
    python stylized_qr.py --data "https://example.com" --logo logo.png --output qr_output.png
"""

import argparse
import math
import qrcode
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Colour palette ──────────────────────────────────────────────────
BG_COLOR = (0, 0, 0)            # Black background
DOT_COLOR = (242, 169, 0)       # Golden-yellow (#F2A900)
FINDER_BG = (0, 0, 0)          # Finder pattern background
FINDER_RING = (242, 169, 0)    # Outer ring of finder
FINDER_INNER = (242, 169, 0)   # Inner square of finder

def generate_qr_matrix(data: str, error_correction=qrcode.constants.ERROR_CORRECT_H):
    """Generate the raw QR boolean matrix."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_correction,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    return matrix

def is_finder_zone(row, col, n):
    """Check if (row, col) belongs to one of the three 7×7 finder patterns."""
    zones = [
        (0, 0),
        (0, n - 7),
        (n - 7, 0),
    ]
    for (r0, c0) in zones:
        if r0 <= row < r0 + 7 and c0 <= col < c0 + 7:
            return True
    return False

def draw_rounded_rect(draw, bbox, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = bbox
    r = radius
    # Draw the main body
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    # Four corner circles
    draw.ellipse([x0, y0, x0 + 2 * r, y0 + 2 * r], fill=fill)
    draw.ellipse([x1 - 2 * r, y0, x1, y0 + 2 * r], fill=fill)
    draw.ellipse([x0, y1 - 2 * r, x0 + 2 * r, y1], fill=fill)
    draw.ellipse([x1 - 2 * r, y1 - 2 * r, x1, y1], fill=fill)

def draw_finder_pattern(draw, cx, cy, cell_size):
    """
    Draw a stylised finder pattern centred at (cx, cy):
    - Outer rounded ring (circle)
    - Gap (background)
    - Inner rounded square
    Mimics the look in the reference image.
    """
    outer_r = cell_size * 3.5
    mid_r = cell_size * 2.5
    inner_r = cell_size * 1.5

    # Outer circle (ring)
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        fill=DOT_COLOR,
    )
    # Middle gap circle (black)
    draw.ellipse(
        [cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r],
        fill=BG_COLOR,
    )
    # Inner rounded square
    half = inner_r
    corner_r = cell_size * 0.45
    draw_rounded_rect(
        draw,
        (cx - half, cy - half, cx + half, cy + half),
        corner_r,
        DOT_COLOR,
    )

def create_stylized_qr(
    data: str,
    logo_path: str | None = None,
    output_path: str = "qr_output.png",
    image_size: int = 512,
    dot_scale: float = 0.5,
):
    """Create the full stylized QR code image."""

    matrix = generate_qr_matrix(data)
    n = len(matrix)

    # Determine cell size and padding for centring
    padding_cells = 2  # quiet zone
    total_cells = n + 2 * padding_cells
    cell_size = image_size / total_cells
    offset = padding_cells * cell_size  # pixel offset for the QR grid

    # Create RGBA canvas
    img = Image.new("RGBA", (image_size, image_size), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # ── 1. Draw data dots (skip finder zones) ──────────────────────
    dot_r = (cell_size * dot_scale) / 2.0

    # Pre-compute logo exclusion zone (centre of QR)
    logo_centre_cells = n / 2.0
    logo_radius_cells = n * 0.16  # how many cells around centre to clear

    for row in range(n):
        for col in range(n):
            if is_finder_zone(row, col, n):
                continue

            # Distance from centre in cell units
            dr = row + 0.5 - logo_centre_cells
            dc = col + 0.5 - logo_centre_cells
            dist = math.sqrt(dr * dr + dc * dc)

            # Skip modules inside logo area
            if dist < logo_radius_cells:
                continue

            if matrix[row][col]:
                cx = offset + (col + 0.5) * cell_size
                cy = offset + (row + 0.5) * cell_size

                # Randomise dot size slightly near the logo edge for a
                # "fade / blend" effect
                fade_start = logo_radius_cells
                fade_end = logo_radius_cells + 2.5
                if dist < fade_end:
                    t = (dist - fade_start) / (fade_end - fade_start)
                    t = max(0.0, min(1.0, t))
                    r = dot_r * (0.3 + 0.7 * t)
                else:
                    r = dot_r

                draw.ellipse(
                    [cx - r, cy - r, cx + r, cy + r],
                    fill=DOT_COLOR + (255,),
                )

    # ── 2. Draw finder patterns ────────────────────────────────────
    finder_positions = [
        (3.5, 3.5),                # top-left
        (3.5, n - 3.5),            # top-right
        (n - 3.5, 3.5),            # bottom-left
    ]
    for (fr, fc) in finder_positions:
        cx = offset + fc * cell_size
        cy = offset + fr * cell_size
        draw_finder_pattern(draw, cx, cy, cell_size)

    # ── 3. Overlay the logo with smooth circular mask ──────────────
    if logo_path:
        logo = Image.open(logo_path).convert("RGBA")

        logo_pixel_radius = int(logo_radius_cells * cell_size)
        logo_diameter = int(logo_pixel_radius * 2)
        logo_resized = logo.resize(
            (logo_diameter, logo_diameter), Image.LANCZOS
        )

        # Create a smooth circular alpha mask with anti-aliased edge
        mask_size = logo_diameter
        # Supersample for smooth edges
        ss = 4
        big = mask_size * ss
        mask_big = Image.new("L", (big, big), 0)
        draw_mask = ImageDraw.Draw(mask_big)

        # Slightly smaller circle to give a blending border
        border = int(cell_size * 0.8) * ss
        draw_mask.ellipse(
            [border, border, big - border, big - border],
            fill=255,
        )
        # Down-sample for anti-aliased edge
        mask = mask_big.resize((mask_size, mask_size), Image.LANCZOS)

        # Optional: add a thin golden ring around the logo
        ring_img = Image.new("RGBA", (mask_size, mask_size), (0, 0, 0, 0))
        ring_draw = ImageDraw.Draw(ring_img)
        ring_border = int(cell_size * 0.3)
        ring_draw.ellipse(
            [ring_border, ring_border,
             mask_size - ring_border, mask_size - ring_border],
            outline=DOT_COLOR + (255,),
            width=max(2, int(cell_size * 0.35)),
        )

        # Draw black filled circle behind logo so data dots don't bleed
        bg_circle = Image.new("RGBA", (mask_size, mask_size), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_circle)
        bg_draw.ellipse(
            [0, 0, mask_size, mask_size],
            fill=BG_COLOR + (255,),
        )

        # Composite: background circle → logo (masked) → ring
        logo_composite = Image.new(
            "RGBA", (mask_size, mask_size), (0, 0, 0, 0)
        )
        logo_composite = Image.alpha_composite(logo_composite, bg_circle)
        logo_masked = Image.new(
            "RGBA", (mask_size, mask_size), (0, 0, 0, 0)
        )
        logo_masked.paste(logo_resized, (0, 0), mask)
        logo_composite = Image.alpha_composite(logo_composite, logo_masked)
        logo_composite = Image.alpha_composite(logo_composite, ring_img)

        # Smooth alpha fringe with Gaussian blur on the alpha channel
        r_chan, g_chan, b_chan, a_chan = logo_composite.split()
        a_smooth = a_chan.filter(ImageFilter.GaussianBlur(radius=2))
        logo_composite = Image.merge("RGBA", (r_chan, g_chan, b_chan, a_smooth))

        # Paste centred
        paste_x = int((image_size - mask_size) / 2)
        paste_y = int((image_size - mask_size) / 2)
        img = Image.alpha_composite(img, Image.new("RGBA", img.size, (0, 0, 0, 0)))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay.paste(logo_composite, (paste_x, paste_y), logo_composite)
        img = Image.alpha_composite(img, overlay)

    # ── 4. Final smooth pass (subtle) ──────────────────────────────
    # Convert to RGB for saving
    final = img.convert("RGB")
    final.save(output_path, "PNG", quality=100)
    print(f"✅  Saved stylized QR code to {output_path}")
    return final

# ── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate a stylized QR code with circular dots, "
                    "rounded finder patterns, and a centred logo."
    )
    parser.add_argument(
        "--data", "-d",
        type=str,
        default="https://example.com",
        help="Data / URL to encode in the QR code.",
    )
    parser.add_argument(
        "--logo", "-l",
        type=str,
        default=None,
        help="Path to a logo image (PNG with transparency recommended).",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="qr_output.png",
        help="Output file path.",
    )
    parser.add_argument(
        "--size", "-s",
        type=int,
        default=512,
        help="Output image size in pixels (square).",
    )
    parser.add_argument(
        "--dot-scale",
        type=float,
        default=0.5,
        help="Dot diameter as fraction of cell size (0.0–1.0).",
    )
    args = parser.parse_args()

    create_stylized_qr(
        data=args.data,
        logo_path=args.logo,
        output_path=args.output,
        image_size=args.size,
        dot_scale=args.dot_scale,
    )

if __name__ == "__main__":
    main()