"""Polish selected packings by linearizing contacts, then try deletion and L borders."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'algorithms'))
from constructions import Candidate
from packing import COLUMNS, Tile, extent
from strip_search import MIN_SIDE_GAIN, _add_borders

VERTICES = np.array([[-.5, -.5], [-.5, .5], [.5, -.5], [.5, .5]])
SIDE_GAIN = 1e-5
CONTACT_GAP = 1e-9
EXPORT_DILATION = 1 + 4e-9


def perpendicular(vectors):
    return np.stack((-vectors[..., 1], vectors[..., 0]), axis=-1)


def vertices(poses):
    axis = np.stack((np.cos(poses[:, 2]), np.sin(poses[:, 2])), axis=1)
    normal = perpendicular(axis)
    offsets = axis[:, None, :]*VERTICES[None, :, :1] + normal[:, None, :]*VERTICES[None, :, 1:]
    return axis, normal, offsets


def enclosing_box(poses):
    points = poses[:, None, :2] + vertices(poses)[2]
    low, high = points.min(axis=(0, 1)), points.max(axis=(0, 1))
    return np.column_stack((poses[:, :2]-low, poses[:, 2])), max(high-low)


def nearby_contacts(poses, distance):
    axis, normal, offsets = vertices(poses)
    left, right = cKDTree(poses[:, :2]).query_pairs(distance, output_type='ndarray').T
    axes = np.stack((axis[left], normal[left], axis[right], normal[right]), axis=1)
    displacement = poses[right, :2]-poses[left, :2]
    projections = np.einsum('ij,iaj->ia', displacement, axes)
    radius = .5 + np.concatenate((
        np.einsum('iaj,ikj->iak', axes[:, :2], offsets[right]).max(axis=2),
        np.einsum('iaj,ikj->iak', axes[:, 2:], offsets[left]).max(axis=2),
    ), axis=1)
    return left, right, axes, projections, radius, offsets


def linear_step(poses, side, trust, time_limit):
    n = len(poses)
    rows, cols, values, margins = [], [], [], []

    def constrain(gap, indices, derivative):
        row_indices = np.arange(len(margins), len(margins)+len(gap))[:, None]
        rows.extend(np.broadcast_to(row_indices, indices.shape).ravel())
        cols.extend(indices.ravel())
        values.extend(-derivative.ravel())
        margins.extend(gap)

    left, right, axes, projections, radius, offsets = nearby_contacts(poses, np.sqrt(2)+5*trust)
    gaps = abs(projections)-radius
    axis_index = gaps.argmax(axis=1)
    pair_index = np.flatnonzero(gaps.max(axis=1) < 6*trust)
    chosen = axis_index[pair_index]
    from_left = chosen < 2
    owner = np.where(from_left, left[pair_index], right[pair_index])
    other = np.where(from_left, right[pair_index], left[pair_index])
    direction = np.sign(projections[pair_index, chosen])
    normals = axes[pair_index, chosen]*(direction*np.where(from_left, 1, -1))[:, None]
    arms = poses[other, None, :2]+offsets[other]-poses[owner, None, :2]
    gap = np.einsum('ij,ikj->ik', normals, arms)-.5
    pair, corner = np.nonzero(gap < 7*trust)
    axis = normals[pair]
    arm = arms[pair, corner]
    own_columns = 3*owner[pair, None]+np.arange(3)
    other_columns = 3*other[pair, None]+np.arange(3)
    # Linearize the face normal and the opposite vertex independently.
    constrain(gap[pair, corner], np.column_stack((own_columns, other_columns)), np.column_stack((
        -axis, (perpendicular(axis)*arm).sum(axis=1),
        axis, (axis*perpendicular(offsets[other[pair], corner])).sum(axis=1),
    )))

    points = poses[:, None, :2]+offsets
    for axis in (0, 1):
        for sign in (1, -1):
            upper_wall = sign == -1
            gap = sign*(points[:, :, axis]-side*upper_wall)
            index, corner = np.nonzero(gap < 4*trust)
            columns = np.column_stack((3*index+axis, 3*index+2, np.full(len(index), 3*n)))
            delta_angle = perpendicular(offsets[index, corner])[:, axis]
            constrain(gap[index, corner], columns, np.column_stack((
                np.full(len(index), sign), sign*delta_angle, np.full(len(index), upper_wall),
            )))

    matrix = coo_matrix((values, (rows, cols)), shape=(len(margins), 3*n+1)).tocsr()
    objective = np.zeros(3*n+1)
    objective[-1] = 1
    options = {'primal_feasibility_tolerance': 1e-9, 'dual_feasibility_tolerance': 1e-9}
    if time_limit:
        options['time_limit'] = time_limit
    result = linprog(objective, A_ub=matrix, b_ub=margins, bounds=(-trust, trust),
                     method='highs', options=options)
    if result.success and result.x[-1] < -1e-9:
        return result.x[:-1].reshape(n, 3)
    return None


def separate(poses):
    _, _, _, projections, radius, _ = nearby_contacts(poses, np.sqrt(2)+1e-7)
    needed = (radius+CONTACT_GAP)/np.maximum(abs(projections), 1e-9)
    poses[:, :2] *= needed.min(axis=1).max(initial=1.)
    return enclosing_box(poses)


def quench(poses, time_limit=0):
    poses, side = enclosing_box(poses)
    for trust in (.006, .003, .0015, .00075, .00025, .00006, .00001):
        for _ in range(8):
            step = linear_step(poses, side, trust, time_limit)
            if step is None:
                break
            candidate, next_side = separate(poses+step)
            if next_side >= side-2e-8:
                break
            poses, side = candidate, next_side
    return poses, side


def polish(work):
    n, baseline, restarts = work
    poses = np.array([(tile.x, tile.y, tile.angle) for tile in baseline.tiles])
    best, side = quench(poses)
    if restarts:
        initial, _ = enclosing_box(poses)
        rng = np.random.default_rng(n)
        for sigma in (.0001, .001, .003):
            candidate, _ = separate(initial+rng.normal(0, sigma, initial.shape))
            candidate, length = quench(candidate, time_limit=1.2)
            if length < side:
                best, side = candidate, length
    best[:, :2] = (best[:, :2]-best[:, :2].mean(axis=0))*EXPORT_DILATION
    tiles = [Tile(*coordinates) for coordinates in best.tolist()]
    side = extent(tiles)
    return n, Candidate(tiles, 'contact-lp', n, {}, side)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--targets', type=int, nargs='+', required=True)
    parser.add_argument('--restart', type=int, nargs='*', default=[])
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Use a separate output CSV')
    with args.input.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            parser.error('Expected a packing CSV')
        groups = {}
        for row in reader:
            groups.setdefault(int(row['n']), []).append(row)
    if set(groups) != set(range(1, 1001)) or any(len(rows) != n for n, rows in groups.items()):
        parser.error('Expected all 1,000 packings with exactly n squares each')
    targets = sorted(set(args.targets)|set(args.restart))
    if any(n not in groups for n in targets):
        parser.error('All targets must be in 1..1000')
    base = {}
    for n, rows in groups.items():
        tiles = [Tile(*(float(row[key]) for key in COLUMNS[3:])) for row in rows]
        base[n] = Candidate(tiles, 'baseline', n, {}, extent(tiles))
    best = base.copy()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, candidate in pool.map(polish, ((n, base[n], n in args.restart) for n in targets)):
            if candidate.side < base[n].side-SIDE_GAIN:
                best[n] = candidate

    for n in range(999, 0, -1):
        next_packing = best[n+1]
        if next_packing.side < best[n].side-MIN_SIDE_GAIN:
            tiles = next_packing.tiles[:n]
            best[n] = Candidate(tiles, 'deletion', next_packing.source_n, {}, extent(tiles))
    best = _add_borders(best)

    with args.output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for n, candidate in sorted(best.items()):
            rows = groups[n]
            if candidate.side < base[n].side-MIN_SIDE_GAIN:
                for row, tile in zip(rows, candidate.tiles):
                    row.update(x=repr(tile.x), y=repr(tile.y), angle=repr(tile.angle))
            writer.writerows(rows)


if __name__ == '__main__':
    main()
