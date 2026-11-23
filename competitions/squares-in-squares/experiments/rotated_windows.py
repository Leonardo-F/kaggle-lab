"""Reuse larger certified packings by cropping and rotating their layouts."""

import argparse
import csv
import math
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

from contact_polish import Candidate, COLUMNS, Tile, _add_borders, enclosing_box, vertices
from clipped_rows import ClippedRows
from core_search import read_witnesses
from tilt_search import StripWitness, make_layout

EXPORT_CLEARANCE = 1 + 12e-9
MIN_GAIN = 1e-6
# Test small rotations where cropping has room to exchange boundary tiles.
WINDOW_ANGLES = np.radians((0, -.5, .5, -1, 1, -2, 2, -3, 3))


def layout_side(poses):
    return enclosing_box(poses)[1]


def rotate(poses, angle):
    sine, cosine = math.sin(angle), math.cos(angle)
    result = poses.copy()
    result[:, :2] = poses[:, :2] @ np.array([[cosine, sine], [-sine, cosine]])
    result[:, 2] += angle
    return result


def tighten_rotation(poses):
    """Minimize the enclosing square over all rigid rotations.

    Between convex-hull edge directions the extreme vertices are fixed. Both
    spans are concave there, so the only interior candidate is where they meet.
    """
    points = (poses[:, None, :2] + vertices(poses)[2]).reshape(-1, 2)
    hull = points[ConvexHull(points).vertices]
    edges = np.roll(hull, -1, axis=0) - hull
    quarter = math.pi / 2
    ends = np.unique(np.r_[0., np.arctan2(edges[:, 1], edges[:, 0]) % quarter, quarter])
    midpoints = (ends[1:] + ends[:-1]) / 2
    axes = np.stack((np.cos(midpoints), np.sin(midpoints)), axis=1)
    projections = axes @ hull.T
    normal_projections = np.stack((-axes[:, 1], axes[:, 0]), axis=1) @ hull.T
    dx = hull[projections.argmax(axis=1)] - hull[projections.argmin(axis=1)]
    dy = hull[normal_projections.argmax(axis=1)] - hull[normal_projections.argmin(axis=1)]
    equal = np.arctan2(dy[:, 1] - dx[:, 0], dx[:, 1] + dy[:, 0]) % math.pi
    angles = np.r_[ends[:-1], equal[(equal > ends[:-1]) & (equal < ends[1:])]]
    axes = np.stack((np.cos(angles), np.sin(angles)), axis=1)
    sides = np.maximum(np.ptp(axes @ hull.T, axis=1),
                       np.ptp(np.stack((-axes[:, 1], axes[:, 0]), axis=1) @ hull.T, axis=1))
    i = sides.argmin()
    return rotate(poses, -angles[i]), sides[i]


class Windows:
    """Compact bit masks for the squares inside candidate axis-aligned windows."""

    def __init__(self, poses):
        half = (np.abs(np.cos(poses[:, 2])) + np.abs(np.sin(poses[:, 2]))) / 2
        self.poses = poses
        self.axes = []
        for coordinate in poses[:, :2].T:
            low = coordinate - half
            high = coordinate + half
            order = low.argsort()
            reverse = high.argsort()[::-1]
            self.axes.append((low[order], order.tolist(), high[reverse], reverse.tolist()))

    @staticmethod
    def exclusions(axis, side, budget):
        low, order, high, reverse = axis
        if high[0] - low[0] <= side:
            return [0]
        masks = []
        left = 0
        for index in range(budget + 1):
            if index == 0 or low[index] != low[index - 1]:
                mask = left
                limit = low[index] + side
                for edge, tile in zip(high, reverse):
                    if edge <= limit:
                        masks.append(mask)
                        break
                    mask |= 1 << tile
                    if mask.bit_count() > budget:
                        break
            left |= 1 << order[index]
        return masks

    def fit(self, n, side):
        budget = len(self.poses) - n
        x_masks = self.exclusions(self.axes[0], side, budget)
        if x_masks:
            for y_mask in self.exclusions(self.axes[1], side, budget):
                for x_mask in x_masks:
                    omitted = x_mask | y_mask
                    if omitted.bit_count() <= budget:
                        return omitted
        return None

    def crop(self, n, limit):
        mask = self.fit(n, limit)
        if mask is None:
            return None
        lo, hi = math.sqrt(n), limit
        for _ in range(20):
            mid = (lo + hi) / 2
            result = self.fit(n, mid)
            if result is None:
                lo = mid
            else:
                hi, mask = mid, result
        indices = [i for i in range(len(self.poses)) if not (mask >> i) & 1]
        return self.poses[indices[:n]]


def constructive_seeds():
    root = Path(__file__).resolve().parents[1] / 'algorithms'
    for _, core in read_witnesses(root / 'core_witnesses.tsv'):
        yield core.layout()
    for line in (root / 'clipped_witnesses.tsv').read_text().splitlines():
        size, side, phase, *corners = line.split()
        yield ClippedRows(int(size), float(side), float(phase), *map(int, corners)).layout()
    for line in (root / 'tilt_witnesses.tsv').read_text().splitlines():
        k, side, _, theta, phase, first, last = line.split()
        witness = StripWitness(int(k), float(theta), float(phase), int(first), int(last))
        yield make_layout(witness, float(side) + 1e-9)


def improve(groups, max_drop, scan_witnesses):
    base = {n: np.array(tiles) for n, tiles in groups.items()}
    best = base.copy()
    lengths = {n: layout_side(tiles) for n, tiles in base.items()}
    origins = {}

    def consider(n, poses, source, method):
        poses, side = tighten_rotation(poses)
        if side > lengths[n] - MIN_GAIN:
            return
        poses[:, :2] *= EXPORT_CLEARANCE
        side = layout_side(poses)
        if side < lengths[n] - MIN_GAIN:
            best[n], lengths[n], origins[n] = poses, side, (source, method)

    def scan(poses, is_base):
        size = len(poses)
        if size in lengths and lengths[size] > math.sqrt(size) + MIN_GAIN:
            consider(size, poses, size, 'rigid rotation')
        angles = WINDOW_ANGLES if is_base else WINDOW_ANGLES[:5]
        for angle in angles:
            window = Windows(rotate(poses, angle))
            for n in range(min(size - 1, 1000), max(1, size - max_drop) - 1, -1):
                # Allow a sub-degree change in angle after the crop.
                limit = lengths[n] - MIN_GAIN + (.012 if angle == 0 else 0.)
                if lengths[n] - math.sqrt(n) <= MIN_GAIN:
                    continue
                crop = window.crop(n, limit)
                if crop is not None:
                    consider(n, crop, size, 'rotated crop')

    for poses in base.values():
        scan(poses, True)
    if scan_witnesses:
        for layout in constructive_seeds():
            poses = np.array([(tile.x, tile.y, tile.angle) for tile in layout])
            scan(poses, False)

    candidates = {n: Candidate([Tile(*v) for v in poses], 'window', n, {}, lengths[n])
                  for n, poses in best.items()}
    extended = _add_borders(candidates)
    for n, candidate in extended.items():
        if candidate.side < lengths[n] - MIN_GAIN:
            lengths[n] = candidate.side
            best[n] = np.array([(tile.x, tile.y, tile.angle) for tile in candidate.tiles])
            origins[n] = (candidate.source_n, 'L border')
    for n, (source, method) in sorted(origins.items()):
        print(f'{n:4d}  {source:4d}  {method:15s}  {layout_side(base[n]):.9f} -> {lengths[n]:.9f}')
    return {n: best[n] for n in origins}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--max-drop', type=int, default=18)
    parser.add_argument('--witnesses', action='store_true', help='Scan alternate constructive layouts')
    args = parser.parse_args()
    if args.output.exists() or args.max_drop < 1:
        parser.error('Use a fresh output path and a positive crop budget')

    with args.input.open(newline='', encoding='utf-8') as stream:
        reader = csv.reader(stream)
        if tuple(next(reader)) != COLUMNS:
            parser.error('Expected a standard packing CSV')
        groups = {n: [] for n in range(1, 1001)}
        for _, count, _, x, y, angle in reader:
            groups[int(count)].append((float(x), float(y), float(angle)))
    if any(len(tiles) != n for n, tiles in groups.items()):
        parser.error('Expected all 1,000 puzzles')
    changed = improve(groups, args.max_drop, args.witnesses)
    with args.input.open(newline='', encoding='utf-8') as source, args.output.open(
            'x', newline='', encoding='utf-8') as output:
        reader, writer = csv.reader(source), csv.writer(output)
        writer.writerow(next(reader))
        for row in reader:
            n = int(row[1])
            if n in changed:
                row[3:] = [repr(float(v)) for v in changed[n][int(row[2])]]
            writer.writerow(row)


if __name__ == '__main__':
    main()
