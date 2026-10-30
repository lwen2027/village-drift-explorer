"""Shared frame for the paper figures: a title at the image's top-left edge and a note at the bottom-left.

A figure script lays out its plot as usual, records its title and note with set_frame(), and writes the file with
save(). save() measures the plot, grows the figure to fit the title above it and the note below it, and moves panel
titles to the image's left edge, so every figure gets the same frame whatever its own layout.
"""

import os
import textwrap
from pathlib import Path

from matplotlib.transforms import Bbox

INK, MUTED = "#292820", "#747168"
TITLE_FONT = "Lora"
MARGIN = 0.12  # inches around the frame
GAP = 0.14  # inches between the title or note and the plot


def bare():
    """Paper mode (FIG_BARE=<dir>): no title or note, since the LaTeX caption carries them; files go to <dir>."""
    return os.environ.get("FIG_BARE")


def set_frame(fig, title=None, note=None, font=8):
    fig._frame = (None, None, font) if bare() else (title, note, font)


def _to_inches(fig):
    """Pin every axes, figure text and figure legend to inches, so resizing the figure leaves them in place."""
    W, H = fig.get_size_inches()
    r = fig.canvas.get_renderer()
    axes = [(ax, ax.get_position(original=True)) for ax in fig.axes]
    texts = []
    for t in fig.texts:
        x, y = t.get_position()
        texts.append((t, x * W, y * H))
    legends = []
    for lg in fig.legends:
        bb = lg.get_bbox_to_anchor().transformed(fig.dpi_scale_trans.inverted())
        legends.append((lg, bb))
    return W, H, axes, texts, legends, r


def _wrap(fig, text, width_in, **kw):
    """Wrap a note to the figure width (manual line breaks are kept)."""
    t = fig.text(0, 0, text, **kw)
    r = fig.canvas.get_renderer()
    w = t.get_window_extent(r).width / fig.dpi
    t.remove()
    if w <= width_in:
        return text
    lines = text.split("\n")
    longest = max(len(line) for line in lines)
    chars = max(20, int(longest * width_in / w) - 2)
    return "\n".join(textwrap.fill(line, chars) for line in lines)


def apply_frame(fig):
    title, note, font = getattr(fig, "_frame", (None, None, 8))
    fig.canvas.draw()
    W, H, axes, texts, legends, r = _to_inches(fig)
    content = fig.get_tightbbox(r)  # inches
    title_kw = dict(fontsize=font + 3, fontfamily=TITLE_FONT, fontweight="semibold", color=INK)
    note_kw = dict(fontsize=font - 1, color=MUTED, linespacing=1.4)
    th = nh = 0.0
    if title:
        t = fig.text(0, 0, title, **title_kw)
        th = t.get_window_extent(r).height / fig.dpi + GAP
        t.remove()
    if note:
        note = _wrap(fig, note, W - 2 * MARGIN, **note_kw)
        t = fig.text(0, 0, note, **note_kw)
        nh = t.get_window_extent(r).height / fig.dpi + GAP
        t.remove()
    new_h = MARGIN + nh + content.height + th + MARGIN
    shift = MARGIN + nh - content.y0
    fig.set_size_inches(W, new_h, forward=False)
    for ax, pos in axes:
        ax.set_position([pos.x0, (pos.y0 * H + shift) / new_h, pos.width, pos.height * H / new_h])
    for t, x, y in texts:
        t.set_transform(fig.dpi_scale_trans)
        t.set_position((x, y + shift))
    for lg, bb in legends:
        lg.set_bbox_to_anchor(Bbox.from_bounds(bb.x0, bb.y0 + shift, bb.width, bb.height), transform=fig.dpi_scale_trans)
    if title:
        fig.text(MARGIN, new_h - MARGIN, title, va="top", transform=fig.dpi_scale_trans, **title_kw)
    if note:
        fig.text(MARGIN, MARGIN, note, va="bottom", transform=fig.dpi_scale_trans, **note_kw)
    # Panel titles in the leftmost column start at the image's left edge too; side-by-side panels keep theirs.
    left = min(ax.get_position().x0 for ax in fig.axes)
    for ax in fig.axes:
        lt = ax._left_title
        pos = ax.get_position()
        if lt.get_text() and pos.x0 - left < 0.01:
            lt.set_x((MARGIN / W - pos.x0) / pos.width)


def save(fig, path, dpi=300):
    apply_frame(fig)
    if bare():
        path = Path(bare()) / Path(path).name
    fig.savefig(path, dpi=dpi)
