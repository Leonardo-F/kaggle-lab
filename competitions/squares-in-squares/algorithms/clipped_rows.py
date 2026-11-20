"""Fit independently sliding 45-degree rows between four corner staircases."""

from dataclasses import asdict, dataclass
import math

from constructions import CLEARANCE_SCALE, Candidate, finish_template
from packing import Tile, extent
from strip_search import MIN_SIDE_GAIN

INV_ROOT_TWO = math.sqrt(0.5)
EPS = 1e-10  # Matches the sweep; finish_template opens the final contacts.


@dataclass(frozen=True)
class ClippedRows:
    capacity: int
    side: float
    phase: float
    bl: int
    tr: int
    br: int
    tl: int

    def layout(self):
        side, s = self.side, INV_ROOT_TWO
        tiles = []
        for depth, right, top in ((self.bl, False, False), (self.tr, True, True),
                                  (self.br, True, False), (self.tl, False, True)):
            for i in range(depth):
                for j in range(depth-i):
                    tiles.append(Tile(side-i-.5 if right else i+.5,
                                      side-j-.5 if top else j+.5))

        # In u=(x+y)/sqrt(2), v=(y-x)/sqrt(2), centres in each row
        # lie one unit apart. The outer box and the corners clip each end.
        diagonal = 2*s*side
        low = (self.bl+1)*s+.5 if self.bl else 0
        high = diagonal-(self.tr+1)*s-.5 if self.tr else diagonal
        k = math.floor(side)
        for j in range(-k, k+1):
            v = j+self.phase
            if self.br and v < (self.br+1-side)*s+.5-EPS:
                continue
            if self.tl and -v < (self.tl+1-side)*s+.5-EPS:
                continue
            left = max(low, 1+abs(v))
            right = min(high, diagonal-1-abs(v))
            count = math.floor(right-left+1+EPS)
            for i in range(count):
                u = (left+right-count+1)/2+i
                tiles.append(Tile((u-v)*s, (u+v)*s, math.pi/4))
        if len(tiles) != self.capacity:
            raise ValueError(f'Clipped-row capacity mismatch: {self}')
        return finish_template(tiles, side)


def add_clipped_rows(baseline, witness_path):
    result = baseline.copy()
    with witness_path.open() as handle:
        for line in handle:
            capacity, side, phase, *corners = line.split()
            w = ClippedRows(int(capacity), float(side), float(phase), *map(int, corners))
            eligible = [n for n in range(math.floor(w.side)**2+1, min(max(result), w.capacity)+1)
                        if w.side*CLEARANCE_SCALE < result[n].side-MIN_SIDE_GAIN]
            if eligible:
                layout = w.layout()
                for n in eligible:
                    tiles = layout[:n]
                    result[n] = Candidate(tiles, 'clipped-rows', w.capacity, asdict(w), extent(tiles))
    return result
