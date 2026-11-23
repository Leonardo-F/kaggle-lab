// Combine upright and tilted lattices by solving their bipartite conflict graph.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numbers>
#include <string>
#include <vector>

namespace {
struct Tile {
    double x, y, angle;
};

using Layout = std::vector<Tile>;
using Graph = std::vector<std::vector<int>>;
constexpr double margin = 2e-8;

int cell(double x) { return static_cast<int>(std::floor(x)); }

Layout upright(int k, double f, double px, double py, int split, bool horizontal) {
    Layout result;
    for (int row = 0; row < k; ++row) {
        for (int col = 0; col < k; ++col) {
            const double dx = split >= 0 && row >= split ? f-px : px;
            Tile tile{.5 + col + dx, .5 + row + py, 0.};
            if (!horizontal) std::swap(tile.x, tile.y);
            result.push_back(tile);
        }
    }
    return result;
}

Layout tilted(double side, double angle, double u, double v) {
    const double c = std::cos(angle), s = std::sin(angle), mid = side / 2;
    const double half = (std::abs(c) + std::abs(s)) / 2;
    const int range = static_cast<int>(std::ceil(side * .72)) + 1;
    Layout tiles;
    for (int i = -range; i <= range; ++i) {
        for (int j = -range; j <= range; ++j) {
            const double x = mid + c*(i+u) - s*(j+v), y = mid + s*(i+u) + c*(j+v);
            if (x >= half && x <= side-half && y >= half && y <= side-half)
                tiles.push_back({x,y,angle});
        }
    }
    return tiles;
}

struct Matching {
    std::vector<int> partner;
    std::vector<int> left;
    std::vector<int> seen;
    int count = 0;

    Matching(const Graph& edges, int right_size)
        : partner(right_size, -1), seen(right_size, -1) {
        for (int i = 0; i < static_cast<int>(edges.size()); ++i) {
            if (augment(edges, i, i)) ++count;
            else left.push_back(i);
        }
    }

    bool augment(const Graph& edges, int i, int step) {
        for (const int j : edges[i]) {
            if (seen[j] == step) continue;
            seen[j] = step;
            if (partner[j] < 0 || augment(edges, partner[j], step)) {
                partner[j] = i;
                return true;
            }
        }
        return false;
    }

    void mark(const Graph& edges, int i, std::vector<bool>& reachable,
              std::vector<bool>& reached_right) const {
        if (reachable[i]) return;
        reachable[i] = true;
        for (const int j : edges[i]) {
            if (partner[j] == i || reached_right[j]) continue;
            reached_right[j] = true;
            if (partner[j] >= 0) mark(edges, partner[j], reachable, reached_right);
        }
    }
};

Layout combine(const Layout& a, const Layout& b, int stride, int lower) {
    std::vector<int> cells(stride*stride, -1);
    for (int i = 0; i < int(a.size()); ++i)
        cells[cell(a[i].x) + stride*cell(a[i].y)] = i;
    Graph edges(b.size());
    const double c = std::cos(b[0].angle), s = std::sin(b[0].angle);
    const double span = .5 * (1 + std::abs(c) + std::abs(s)) + margin;
    for (int i = 0; i < int(b.size()); ++i) {
        const auto& tile = b[i];
        for (int x = std::max(0,cell(tile.x)-1); x <= std::min(stride-1,cell(tile.x)+1); ++x) {
            for (int y = std::max(0,cell(tile.y)-1); y <= std::min(stride-1,cell(tile.y)+1); ++y) {
                const int j = cells[x+stride*y];
                if (j < 0) continue;
                const double dx = a[j].x - tile.x, dy = a[j].y - tile.y;
                if (std::max({std::abs(dx),std::abs(dy),std::abs(c*dx+s*dy),std::abs(-s*dx+c*dy)}) < span)
                    edges[i].push_back(j);
            }
        }
    }
    Matching matching(edges, a.size());
    if (int(a.size()+b.size()) - matching.count <= lower) return {};
    std::vector<bool> reached_left(b.size()), reached_right(a.size());
    for (const int i : matching.left) matching.mark(edges, i, reached_left, reached_right);
    Layout chosen;
    for (int i = 0; i < int(a.size()); ++i)
        if (!reached_right[i]) chosen.push_back(a[i]);
    for (int i = 0; i < int(b.size()); ++i)
        if (reached_left[i]) chosen.push_back(b[i]);
    return chosen;
}

Layout search(int k, double f, int minimum) {
    std::vector<Layout> grids;
    for (double px : {0., .5, 1.})
        for (double py : {0., .5, 1.})
            grids.push_back(upright(k, f, px*f, py*f, -1, true));
    for (int split : {k/3, k/2, 2*k/3}) {
        for (double phase : {0., 1.}) {
            grids.push_back(upright(k, f, phase*f, 0, split, true));
            grids.push_back(upright(k, f, phase*f, 0, split, false));
        }
    }
    Layout best;
    for (double degrees = 8; degrees <= 45; degrees += .5) {
        const double angle = degrees * std::numbers::pi / 180;
        for (int a = 0; a < 8; ++a) {
            for (int b = 0; b < 8; ++b) {
                const auto rotated = tilted(k+f, angle, a/8., b/8.);
                if (rotated.empty()) continue;
                for (const auto& grid : grids) {
                    auto next = combine(grid, rotated, k+1, minimum);
                    if (!next.empty()) {
                        minimum = next.size();
                        best = std::move(next);
                    }
                }
            }
        }
    }
    return best;
}
}

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) return 2;
    const int k = std::stoi(argv[1]);
    if (k < 2 || k > 31) return 2;
    const int shell = k*k;
    int minimum = shell;
    std::cout << std::setprecision(17);
    const std::vector<double> fractions = argc == 3
        ? std::vector<double>{std::stod(argv[2])}
        : std::vector<double>{.65,.73,.80,.86,.91,.95,.975,.995};
    for (const double f : fractions) {
        if (!(f>0 && f<1)) return 2;
        const auto result = search(k,f,minimum);
        if (result.empty()) continue;
        minimum = result.size();
        std::cout << 'n' << ' ' << minimum << ' ' << k+f << '\n';
        const double mid = (k+f)/2;
        for (const auto& tile : result)
            std::cout << (tile.x-mid)*(1.+margin) << ' ' << (tile.y-mid)*(1.+margin)
                << ' ' << tile.angle << '\n';
        std::cout.flush();
    }
}
