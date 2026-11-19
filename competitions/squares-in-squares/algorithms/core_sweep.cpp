// Enumerate 45-degree rectangular cores and four independent corner staircases.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <vector>

namespace {
constexpr int max_n = 1000;
constexpr double inv_root_two = 0.7071067811865475244;
constexpr double epsilon = 1e-10;

struct Corners {
    int first, opposite, count;
    double low, high;
};

struct Layout {
    double side = 1e9;
    int capacity = 0, p = 0, q = 0, right = 0, top = 0;
    int bl = 0, br = 0, tl = 0, tr = 0;
};

int triangle(int depth) { return depth*(depth + 1)/2; }

// Bounds are [low, 2L-high] for x+y, and [low-L, L-high] for y-x.
std::vector<Corners> opposite_pairs(int limit, double projection, double diameter,
                                    double first_offset, double opposite_offset, double ceiling) {
    std::vector<Corners> pairs;
    for (int first = 0; first <= limit; ++first) {
        const double low = first_offset + (first ? first + 1 + projection : diameter);
        for (int opposite = 0; opposite <= limit; ++opposite) {
            const double high = opposite_offset
                + (opposite ? opposite + 1 + projection : diameter);
            if (low + high < 2*ceiling)
                pairs.push_back({first, opposite, triangle(first) + triangle(opposite), low, high});
        }
    }
    std::stable_sort(pairs.begin(), pairs.end(), [](const Corners& a, const Corners& b) {
        return a.count > b.count;
    });
    return pairs;
}

void search_core(int k, int right, int top, int p, int q, std::vector<Layout>& best) {
    const int width = k - right, height = k - top;
    const int interior_grid = width*height, rim = k*k - interior_grid;
    const int limit = std::min(width, height);
    const double a = p*inv_root_two, b = q*inv_root_two, diam = a+b, ceiling = k+1;
    const auto u = opposite_pairs(limit, a, diam, 0, right+top, ceiling);
    const auto v = opposite_pairs(limit, b, diam, right, top, ceiling);
    if (u.empty() || v.empty()) return;
    for (const Corners& sum : u) {
        if (sum.count + v.front().count + p*q <= interior_grid) break;
        for (const Corners& diff : v) {
            const int capacity = sum.count + diff.count + p*q + rim;
            if (capacity <= k*k) break;
            if (sum.first + diff.first > width || sum.opposite + diff.opposite > width ||
                sum.first + diff.opposite > height || sum.opposite + diff.first > height)
                continue;
            // Eliminate y-x then x+y from the core and container constraints.
            const double lower = std::max(diam, sum.low);
            const double falling = std::max(diff.low, diff.high) + diam;
            const double upper = std::max(right+top+diam, sum.high);
            const double rising = std::max(2*top+diam+diff.low, 2*right+diam+diff.high);
            const double side = std::max({double(k), std::max(right,top)+diam,
                (diff.low+diff.high)/2, (lower+upper)/2, (lower+rising)/3,
                (falling+upper)/3, (falling+rising)/4});
            if (side >= ceiling - epsilon) continue;
            for (int n = k*k + 1; n <= std::min(capacity, max_n); ++n) {
                if (side < best[n].side - epsilon)
                    best[n] = {side, capacity, p, q, right, top,
                               sum.first, diff.first, diff.opposite, sum.opposite};
            }
        }
    }
}
}

int main() {
    std::vector<Layout> square(max_n+1), rectangle(max_n+1);
    for (int k = 2; k*k < max_n; ++k) {
        // Compare both families with identical rim and corner-width bounds.
        for (int right = 0; right <= std::min(2,k-1); ++right) {
            for (int top = 0; top <= std::min(right,2-right); ++top) {
                const int max_sum = std::floor((k+1-right)/inv_root_two);
                for (int p = 1; p <= max_sum/2; ++p) {
                    search_core(k,right,top,p,p,square);
                    for (int q = p+1; q <= max_sum-p; ++q)
                        search_core(k,right,top,p,q,rectangle);
                }
            }
        }
        for (int n = k*k + 1; n <= std::min(max_n, (k+1)*(k+1)); ++n) {
            for (const Layout* w : {&square[n], &rectangle[n]}) {
                if (w->capacity == 0) continue;
                std::cout << n << ' ' << std::setprecision(17) << w->side << ' '
                          << w->capacity << ' ' << w->p << ' ' << w->q << ' '
                          << w->right << ' ' << w->top << ' ' << w->bl << ' ' << w->br
                          << ' ' << w->tl << ' ' << w->tr << '\n';
            }
        }
        std::cout.flush();
    }
}
