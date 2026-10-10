"""Draw the eight print figures using only the adjacent fig_data.json."""
import json
import re
import struct
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
from matplotlib.patches import FancyBboxPatch
from matplotlib.text import Text
import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "fig_data.json").read_text(encoding="utf-8-sig"))
FONT = Path(r"C:\Windows\Fonts\msjh.ttc")
font_manager.fontManager.addfont(str(FONT))
FAMILY = font_manager.FontProperties(fname=str(FONT)).get_name()
COLORS = DATA["colors"]
INK = COLORS["ink"]
GRAY = COLORS["gray"]
DPI = 300
plt.rcParams.update({
    "font.family": FAMILY, "font.size": 7.5,
    "axes.labelsize": 8, "axes.titlesize": 9, "axes.titleweight": "bold",
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": COLORS["sub"],
    "xtick.color": INK, "ytick.color": INK,
    "axes.linewidth": .6, "lines.linewidth": 1.2,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "savefig.bbox": None,
    "axes.unicode_minus": False, "hatch.linewidth": .5,
})

OUTPUTS = []


def figure(key, height_factor=1.00):
    size = DATA["display_cm"][key]
    assert .85 <= height_factor <= 1.00
    # PNG widths truncate to whole pixels; cap height at the Word display ratio too.
    width_px = int(size["width"] / 2.54 * DPI)
    height_px = int(width_px * size["current_height"] * height_factor / size["width"])
    fig = plt.figure(figsize=(size["width"] / 2.54,
                              (height_px + .001) / DPI), dpi=DPI)
    fig.display_size = size
    return fig


def color(axis, role):
    return COLORS[axis][role] if role in ("axis", "axis_dark") else GRAY


def marker(label, role=""):
    if "梯度提升" in label or role == "axis_dark":
        return "s"
    return "D" if role == "baseline" else "o"


def style(ax, grid=True):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.tick_params(axis="x", length=2.5, pad=3)
    ax.set_axisbelow(True)
    if grid:
        ax.grid(axis="x", color="#e4e4e4", linewidth=.45)


def text(fig, x, y, value, **kwargs):
    return fig.text(x, y, value, fontsize=kwargs.pop("fontsize", 7.5), **kwargs)


def title(fig, x, y, value):
    return text(fig, x, y, value, fontsize=9, weight="bold", va="top", linespacing=1.3)


def interval(ax, y, mean, limits, c, symbol="o", hollow=False, dashed=False):
    if limits is not None:
        ax.plot(limits, [y, y], color=c, lw=1.25,
                ls="--" if dashed else "-", solid_capstyle="butt")
        ax.plot(limits, [y, y], ls="none", marker="|", ms=4, mew=.8, color=c)
    ax.plot(mean, y, marker=symbol, ms=4.2, ls="none", color=c,
            mfc="white" if hollow else c, mec=c if hollow else INK, mew=.65, zorder=4)


def row_text(ax, y, value, x, **kwargs):
    return ax.text(x, y, value, transform=ax.get_yaxis_transform(),
                   fontsize=7.5, va="center", clip_on=False, **kwargs)


def wrap_width(fig, value, width_fraction, size=7.5, bold=False):
    """Insert only line breaks; retain every character supplied by the JSON."""
    renderer = fig.canvas.get_renderer()
    prop = font_manager.FontProperties(family=FAMILY, size=size,
                                       weight="bold" if bold else "normal")
    max_width = fig.bbox.width * width_fraction
    lines = []
    for original in value.split("\n"):
        current = ""
        for phrase in re.split(r"(?<=，)|(?=→)", original):
            candidate = current + phrase
            if current and renderer.get_text_width_height_descent(candidate, prop, False)[0] > max_width:
                lines.append(current)
                current = phrase
            else:
                current = candidate
        lines.append(current)
    wrapped = "\n".join(lines)
    assert wrapped.replace("\n", "") == value.replace("\n", "")
    return wrapped


def save(fig, filename):
    """Check physical size, typography, text collisions and canvas clipping."""
    fig.canvas.draw()
    assert .85 <= fig.get_figheight() * 2.54 / fig.display_size["current_height"] <= 1.000001
    assert abs(fig.get_figwidth() * 2.54 - fig.display_size["width"]) < 1e-8
    renderer = fig.canvas.get_renderer()
    outside_ticks = set()
    for ax in fig.axes:
        for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not min(limits) <= tick.get_loc() <= max(limits):
                    outside_ticks.update((tick.label1, tick.label2))
    text_boxes = []
    for item in fig.findobj(Text):
        if not item.get_visible() or not item.get_text() or item in outside_ticks:
            continue
        assert not re.search(r"[vV]\d|版本|舊版|新版", item.get_text()), item.get_text()
        assert item.get_fontsize() >= 7.5, item.get_text()
        box = item.get_window_extent(renderer)
        # Ignore invisible tick labels that Matplotlib retains beyond the axis limits.
        if item in [t for ax in fig.axes for t in ax.get_xticklabels() + ax.get_yticklabels()]:
            if not box.overlaps(fig.bbox):
                continue
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1:
            raise ValueError(f"Text outside canvas: {filename}: {item.get_text()!r}")
        for other, other_box in text_boxes:
            if (min(box.x1, other_box.x1) - max(box.x0, other_box.x0) > 1
                    and min(box.y1, other_box.y1) - max(box.y0, other_box.y0) > 1):
                raise ValueError(f"Text overlap: {filename}: {item.get_text()!r} / {other!r}")
        text_boxes.append((item.get_text(), box))
    for ax in fig.axes:
        for label in (ax.xaxis.label, ax.yaxis.label):
            if label.get_text():
                assert 8 <= label.get_fontsize() <= 8.5
        legend = ax.get_legend()
        if legend is not None:
            for note in [legend, *ax.texts]:
                box = note.get_window_extent(renderer).padded(2)
                for line in ax.lines:
                    path = line.get_transform().transform_path(line.get_path())
                    assert not path.intersects_bbox(box, filled=False), f"Annotation covers line: {filename}"
    path = ROOT / filename
    fig.savefig(path, dpi=DPI)
    with path.open("rb") as stream:
        header = stream.read(24)
    width, height = struct.unpack(">II", header[16:24])
    expected = fig.get_size_inches() * DPI
    assert abs(width - expected[0]) < 1.1 and abs(height - expected[1]) < 1.1
    assert fig.display_size["width"] * height / width <= fig.display_size["current_height"]
    OUTPUTS.append((path, width, height))
    plt.close(fig)


def draw_flow():
    d = DATA["圖二"]
    fig = figure("圖二")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")

    def box(x, y, w, h, value, edge=GRAY, size=8):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                  boxstyle="round,pad=0.006,rounding_size=0.008",
                                  edgecolor=edge, facecolor="white", linewidth=.9))
        ax.text(x + w / 2, y + h / 2, value, ha="center", va="center",
                fontsize=size, linespacing=1.5)

    def arrow(start, end):
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "-|>", "lw": .9, "color": COLORS["sub"]})

    box(.13, .855, .74, .12, d["top_box"])
    arrow((.5, .85), (.5, .80))
    box(.025, .665, .95, .125, d["kidney_box"], size=7.5)
    for i, entry in enumerate(d["label_boxes"]):
        x = .025 + i * .495
        arrow((.5, .659), (x + .225, .609))
        box(x, .438, .455, .16, entry["text"], COLORS[entry["axis"]]["axis"], 7.5)
    text(fig, .5, .397, d["note"], ha="center", va="center")
    text(fig, .05, .342, d["fix_box_title"], weight="bold", va="top")
    cursor = .298
    line_height = 9.5 / (fig.get_figheight() * 72)
    for item in d["fix_box_items"]:
        wrapped = wrap_width(fig, item, .90)
        last_item = text(fig, .05, cursor, wrapped, va="top", linespacing=1.25)
        cursor -= line_height * len(wrapped.splitlines()) + .010
    bottom = last_item.get_window_extent(fig.canvas.get_renderer()).y0 / fig.bbox.height - .015
    box(.025, bottom, .95, .362 - bottom, "")
    crop = max(0, bottom - .025)
    assert .85 <= 1 - crop <= 1
    # Remove only the unused bottom strip, preserving all existing physical positions.
    for item in fig.texts:
        x, y = item.get_position()
        item.set_position((x, (y - crop) / (1 - crop)))
    fig.set_figheight(fig.get_figheight() * (1 - crop))
    ax.set_position([0, -crop / (1 - crop), 1, 1 / (1 - crop)])
    save(fig, "圖二_分析樣本與資料修正.png")


def draw_discrimination():
    fig = figure("圖三")
    for r, (axis, d) in enumerate(DATA["圖三"].items()):
        top = .978 - r * .485
        bottom = .59 - r * .485
        for col, metric in enumerate(("auroc", "ap")):
            rows = d[metric]
            assert len(rows) == 6
            prefix = f"({'a' if col == 0 else 'b'}{r + 1}) "
            suffix = "AUROC" if col == 0 else "平均精確率（AP）"
            title(fig, .015 if col == 0 else .51, top, prefix + d["title"] + "：" + suffix)
            ax = fig.add_axes([.300 if col == 0 else .655, bottom, .222 if col == 0 else .255, .295])
            ax.set_ylim(5.65, -.65)
            ax.set_yticks([])
            style(ax)
            if col == 0:
                ax.set(xlim=(.48, .87), xticks=[.5, .6, .7, .8])
                reference = .5
                ref_label = "亂猜"
            else:
                reference = d["prevalence"]
                largest = max(row["max"] for row in rows)
                ax.set_xlim(0 if r == 0 else .32, largest * 1.11)
                ax.xaxis.set_major_locator(ticker.MaxNLocator(4))
                ref_label = f"盛行率 {reference:.3f}"
            ax.axvline(reference, color=COLORS["sub"], ls="--", lw=.8)
            ax.text(reference, 1.015, ref_label, transform=ax.get_xaxis_transform(),
                    ha="left", va="bottom", fontsize=7.5)
            for y, row in enumerate(rows):
                interval(ax, y, row["mean"], [row["min"], row["max"]],
                         color(axis, row["role"]), marker(row["label"], row["role"]),
                         hollow=row["role"] in ("gray", "baseline"))
                if col == 0:
                    row_text(ax, y, row["label"], -1.29, ha="left")
                row_text(ax, y, f'{row["mean"]:.3f}', 1.07)
    save(fig, "圖三_判別力.png")


def draw_calibration():
    fig = figure("圖四")
    for r, (axis, d) in enumerate(DATA["圖四"].items()):
        offset = r * .495
        title(fig, .025, .987 - offset, f"(a{r + 1}) {d['title']}：校準曲線")
        title(fig, .565, .987 - offset, f"(b{r + 1}) 三段分區之實際陽性比例")
        left = fig.add_axes([.095, .605 - offset, .345, .320])
        right = fig.add_axes([.59, .605 - offset, .385, .320])
        style(left)
        style(right, False)
        left.set_xlabel("平均預測機率", labelpad=3)
        left.set_ylabel("實際陽性比例", labelpad=4)
        right.set_ylabel("實際陽性比例", labelpad=4)
        limit = .105 if r == 0 else 1
        left.set(xlim=(0, limit), ylim=(0, min(1, limit * 1.2)))
        left.xaxis.set_major_locator(ticker.MaxNLocator(3))
        left.yaxis.set_major_locator(ticker.MaxNLocator(3))
        left.plot([0, limit], [0, limit], ls="--", color=GRAY, lw=.8)
        handles = []
        categories = list(d["models"][0]["bands"])
        peak = max(b["observed_rate"] for m in d["models"] for b in m["bands"].values())
        right.set_ylim(0, peak * 1.63)
        right.set_xlim(-.65, len(categories) - .35)
        right.set_xticks(range(len(categories)), [
            name + "\n" + "／".join(f'{m["bands"][name]["n"]:,}' for m in d["models"])
            for name in categories])
        text(fig, .59, .523 - offset, "n：邏輯迴歸／梯度提升", va="top")
        right.yaxis.set_major_formatter(ticker.PercentFormatter(1, decimals=0))
        right.yaxis.set_major_locator(ticker.MaxNLocator(3))
        for j, model in enumerate(d["models"]):
            c = color(axis, model["role"])
            curve = model["curve"]
            line, = left.plot([p["mean_pred"] for p in curve], [p["observed"] for p in curve],
                              color=c, ls="-" if j == 0 else "--", marker="o" if j == 0 else "s",
                              ms=2.8, mew=.4)
            handles.append(line)
            xs = np.arange(len(categories)) + (j - .5) * .42
            bands = [model["bands"][name] for name in categories]
            right.bar(xs, [b["observed_rate"] for b in bands], width=.36,
                      color=c, edgecolor=INK, linewidth=.45, hatch="" if j == 0 else "///")
            for x, band in zip(xs, bands):
                padding = 1 if band["observed_rate"] < d["prevalence"] / 2 else 3
                label_y = (band["observed_rate"] if padding == 1
                           else max(band["observed_rate"], d["prevalence"]))
                right.annotate(f'{band["observed_rate"]:.1%}',
                               (x, label_y), xytext=(0, padding), textcoords="offset points",
                               ha="center", va="bottom", fontsize=7.5, linespacing=1.15,
                               bbox={"facecolor": "white", "edgecolor": "none", "pad": .5})
        left.legend(handles, [f'{m["label"]}\n截距 {m["intercept"]:+.2f}、斜率 {m["slope"]:.2f}'
                              for m in d["models"]], loc="upper left",
                    frameon=False, borderaxespad=.2, borderpad=0,
                    handlelength=1.5, labelspacing=.25, handletextpad=.4)
        legend_handles = [plt.Rectangle((0, 0), 1, 1, facecolor=color(axis, m["role"]),
                                       edgecolor=INK, linewidth=.45, hatch="" if j == 0 else "///")
                          for j, m in enumerate(d["models"])]
        right.legend(legend_handles, [m["label"] for m in d["models"]],
                     loc="upper right", frameon=False,
                     borderaxespad=.2, labelspacing=.35)
        right.axhline(d["prevalence"], ls="--", color=COLORS["sub"], lw=.8)
        right.annotate(f'盛行率 {d["prevalence"]:.1%}',
                       (.99, d["prevalence"]), xycoords=right.get_yaxis_transform(),
                       xytext=(0, 3), textcoords="offset points",
                       ha="right", va="bottom", fontsize=7.5)
    save(fig, "圖四_校準與分區.png")


def draw_robustness():
    fig = figure("圖五")
    for col, (axis, d) in enumerate(DATA["圖五"].items()):
        shift = col * .505
        title(fig, .015 + shift, .98, d["title"])
        ax = fig.add_axes([.221 + shift, .19, .207, .70])
        ax.set(xlim=(.67, .88), ylim=(9.7, -.55), yticks=[], xticks=[.7, .75, .8, .85])
        ax.set_xlabel("AUROC", labelpad=3)
        style(ax)
        assert sum(len(m["conditions"]) for m in d["models"]) == 8
        for j, model in enumerate(d["models"]):
            start = j * 5
            row_text(ax, start, model["label"], -.995, weight="bold")
            ax.axvline(model["conditions"][0]["auroc"], color=color(axis, model["role"]),
                       lw=.65, ls=":" if j == 0 else "--", alpha=.55)
            for i, row in enumerate(model["conditions"]):
                y = start + i + 1
                interval(ax, y, row["auroc"], row["ci95"], color(axis, model["role"]),
                         marker(model["label"]), dashed=j == 1)
                row_text(ax, y, row["label"], -.995)
                row_text(ax, y, f'{row["auroc"]:.3f}', 1.045)
            if j == 0:
                ax.axhline(start + 4.5, color="#dddddd", lw=.5, xmin=-1, xmax=1.35, clip_on=False)
    save(fig, "圖五_穩健性.png")


def draw_external():
    fig = figure("圖六")
    for col, (axis, d) in enumerate(DATA["圖六"].items()):
        shift = col * .505
        title(fig, .015 + shift, .975, d["title"])
        ax = fig.add_axes([.208 + shift, .165, .222, .70])
        ax.set(xlim=(.47, .89), ylim=(6.9, -.65), yticks=[], xticks=[.5, .6, .7, .8])
        ax.set_xlabel("AUROC", labelpad=4)
        style(ax)
        ax.axvline(.5, color=COLORS["sub"], lw=.8, ls="--")
        assert [len(g["rows"]) for g in d["groups"]] == [2, 3]
        for j, group in enumerate(d["groups"]):
            start = 0 if j == 0 else 3.6
            row_text(ax, start, group["name"].replace("（", "\n（", 1), -.87,
                     weight="bold", linespacing=1.05)
            for i, row in enumerate(group["rows"]):
                y = start + i + 1
                interval(ax, y, row["auroc"], row["ci95"], color(axis, row["role"]),
                         marker(row["label"], row["role"]), hollow=row["role"] in ("gray", "baseline"))
                row_text(ax, y, row["label"], -.87)
                row_text(ax, y, f'{row["auroc"]:.3f}', 1.035)
    save(fig, "圖六_外部資料.png")


def draw_decision():
    fig = figure("圖七")
    for col, (axis, d) in enumerate(DATA["圖七"].items()):
        shift = col * .50
        title(fig, .02 + shift, .98, d["title"])
        ax = fig.add_axes([.105 + shift, .18, .375, .70])
        style(ax)
        ax.set_xlabel("閾值機率", labelpad=3)
        ax.set_ylabel("淨效益", labelpad=3)
        ax.set_xlim(min(d["pt"]), max(d["pt"]))
        ax.xaxis.set_major_formatter(ticker.PercentFormatter(1, decimals=1 if col == 0 else 0))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(4))
        # Focus on the clinically useful near-zero range; test-all continues below the canvas.
        model_peak = max(max(c["net_benefit"]) for c in d["curves"][:2])
        ax.set_ylim(-model_peak * .20, model_peak * 1.85)
        ax.yaxis.set_major_locator(ticker.MaxNLocator(4, prune="both"))
        handles = []
        for j, curve in enumerate(d["curves"]):
            assert len(curve["net_benefit"]) == len(d["pt"])
            c = color(axis, curve["role"]) if j < 2 else (GRAY if j == 2 else INK)
            line, = ax.plot(d["pt"], curve["net_benefit"], color=c,
                            ls=("-", "--", ":", "-")[j], lw=1.2 if j < 3 else .8,
                            marker=("o", "s", None, None)[j], markersize=2.6, markevery=3)
            handles.append(line)
        ax.legend(handles, [c["label"] for c in d["curves"]], loc="upper right",
                  frameon=False, borderaxespad=.2,
                  ncol=1, labelspacing=.20, handlelength=1.5, handletextpad=.4)
        ax.text(.98, .66, d["annotation"]["text"], transform=ax.transAxes,
                ha="right", va="top", fontsize=7.5, linespacing=1.2)
    save(fig, "圖七_決策曲線.png")


def draw_exposure():
    d = DATA["圖八"]
    fig = figure("圖八")
    blood, urine = "#75459a", "#24766b"
    starts = [.287, .53, .773]
    for col, label in enumerate(d["columns"]):
        wrapped = label.replace("（", "\n（", 1)
        title(fig, starts[col] + .065, .975, wrapped).set_ha("center")
    for r, row in enumerate(d["rows"]):
        bottom = .55 - r * .415
        title(fig, .015, .835 - r * .415, f'{row["metal"]}　n = {row["n_both"]:,}')
        for col, rows in enumerate(row["panels"]):
            assert len(rows) == 4
            ax = fig.add_axes([starts[col], bottom, .157, .245])
            ax.set_xscale("log")
            ax.set(xlim=(.5, 2), ylim=(3.6, -.6), yticks=[])
            ax.xaxis.set_major_locator(ticker.FixedLocator([.5, 1, 2]))
            ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%g"))
            ax.xaxis.set_minor_locator(ticker.NullLocator())
            style(ax)
            ax.axvline(1, color=COLORS["sub"], ls="--", lw=.8)
            for y, entry in enumerate(rows):
                is_blood = entry["kind"] == "blood"
                interval(ax, y, entry["or"], entry["ci95"], blood if is_blood else urine,
                         "D" if is_blood else "o", hollow=not is_blood)
                if col == 0:
                    row_text(ax, y, entry["label"], -1.73)
                row_text(ax, y, f'{entry["or"]:.2f}', 1.055)
    text(fig, .5, .021, d["x_label"], ha="center", va="bottom", fontsize=8)
    save(fig, "圖八_暴露血尿比較.png")


def draw_recalibration():
    fig = figure("圖九", 1)
    for col, (axis, d) in enumerate(DATA["圖九"].items()):
        shift = col * .505
        title(fig, .02 + shift, .95,
              f'{d["title"]}\n測試半陽性中位數 {d["n_pos_test_median"]:.0f} 人')
        ax = fig.add_axes([.17 + shift, .29, .30, .43])
        ax.set_xscale("log")
        ax.set(xlim=(.2, 5), ylim=(1.6, -.6), yticks=[])
        ax.xaxis.set_major_locator(ticker.FixedLocator([.25, .5, 1, 2, 4]))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%g"))
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        style(ax)
        ax.axvline(1, color=COLORS["sub"], lw=.8, ls="--")
        assert len(d["rows"]) == 2
        for y, row in enumerate(d["rows"]):
            interval(ax, y, row["median"], [row["p2_5"], row["p97_5"]],
                     color(axis, row["role"]), "o" if y == 0 else "s", hollow=y == 0)
            row_text(ax, y, row["label"], -.5)
            ax.annotate(f'{row["median"]:.2f}（{row["p2_5"]:.2f}–{row["p97_5"]:.2f}）',
                        (row["median"], y), xytext=(0, 9), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.5,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": .6})
    text(fig, .5, .085, "測試半：平均預測／實際陽性比例（1＝完全校準；對數刻度）",
         ha="center", va="bottom", fontsize=8)
    save(fig, "圖九_重新校準交叉驗證.png")


def main():
    for draw in (draw_flow, draw_discrimination, draw_calibration, draw_robustness,
                 draw_external, draw_decision, draw_exposure, draw_recalibration):
        draw()
    assert len(OUTPUTS) == 8
    for path, width, height in OUTPUTS:
        size = DATA["display_cm"][path.name.split("_")[0]]
        print(f"{path}\t{width} x {height} px\t"
              f"height at {size['width']:g} cm width: {size['width'] * height / width:.4f} cm")
    print(Path(__file__).resolve())


if __name__ == "__main__":
    main()
