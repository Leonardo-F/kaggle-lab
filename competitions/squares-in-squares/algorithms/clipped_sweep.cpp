// Find 45-degree rows clipped by the box and by four axis-aligned staircases.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {
constexpr double s = 0.7071067811865475244, eps = 1e-10;
constexpr int limit = 1000, max_k = 31, max_rows = 2*max_k + 1;
struct Witness {
    int count = 0, bl = 0, tr = 0, br = 0, tl = 0;
    double side = 0, phase = 0;
};
int triangle(int depth) { return depth*(depth+1)/2; }

Witness best_at(int k, double side) {
    const double diagonal = 2*s*side;
    // A row may move until the tile count changes at a wall or a staircase.
    // Modulo the unit row pitch, the two-wall endpoints alternate by 1/2.
    std::vector<double> phases = {-diagonal/2, .5-diagonal/2};
    for (int depth = 1; depth <= k; ++depth) {
        phases.push_back((depth+1-side)*s+.5);
        phases.push_back((depth+1)*s+.5-diagonal);
    }

    Witness best;
    for (double offset : phases) {
        double phase = offset-std::floor(offset);
        int first[max_k+1], end[max_k+1];  // row indices shifted by k
        first[0] = 0;
        end[0] = 2*k+1;
        for (int d = 1; d <= k; ++d) {
            double bound = (d+1-side)*s+.5;
            first[d] = std::clamp(k+int(std::ceil(bound-phase-eps)), 0, 2*k+1);
            end[d] = std::clamp(k+1+int(std::floor(-bound-phase+eps)), 0, 2*k+1);
        }
        double abs_v[max_rows];
        for (int j = 0; j <= 2*k; ++j) abs_v[j] = std::abs(j-k+phase);
        for (int bl = 0; bl <= k; ++bl) {
            const double low = bl ? (bl+1)*s+.5 : 0;
            // A half-turn exchanges bl with tr, and br with tl.
            for (int tr = bl; tr <= k; ++tr) {
                const double high = tr ? diagonal-(tr+1)*s-.5 : diagonal;
                if (high < low-eps) break;
                int prefix[max_rows+1] = {};
                for (int j = 0; j <= 2*k; ++j) {
                    const double left = std::max(low, 1+abs_v[j]);
                    const double right = std::min(high, diagonal-1-abs_v[j]);
                    prefix[j+1] = prefix[j]+std::max(0, int(std::floor(right-left+1+eps)));
                }
                // Adjacent staircases must fit along their shared wall.
                int max_depth = k-tr;
                int best_br[max_k+1] = {};
                for (int br = 1; br <= max_depth; ++br) {
                    int prev = best_br[br-1];
                    int gain = triangle(br)-prefix[first[br]];
                    int previous_gain = triangle(prev)-prefix[first[prev]];
                    best_br[br] = gain > previous_gain ? br : prev;
                }
                // Keep at least one rotated square between the two end corners.
                int last = max_depth;
                for (int tl = 0; tl <= max_depth; ++tl) {
                    while (last >= 0 && prefix[first[last]] >= prefix[end[tl]]) --last;
                    if (last < 0) break;
                    int br = best_br[last];
                    int count = prefix[end[tl]] - prefix[first[br]]
                        + triangle(bl)+triangle(tr)+triangle(br)+triangle(tl);
                    if (count > best.count)
                        best = {count, bl, tr, br, tl, side, phase};
                }
            }
        }
    }
    return best;
}
}

int main(int argc, char** argv) {
    int first_k = argc > 1 ? std::stoi(argv[1]) : 2;
    int last_k = argc > 2 ? std::stoi(argv[2]) : max_k;
    if (first_k < 1 || first_k > last_k || last_k > max_k) return 1;
    for (int k = first_k; k <= last_k; ++k) {
        auto peak = best_at(k, k+1-1e-7);
        int n = k*k+1;
        double lower = k;
        while (n <= std::min(limit,peak.count)) {
            auto winner = peak;
            double upper = winner.side;
            while (upper-lower > 2e-7) {
                auto trial = best_at(k, (upper+lower)/2);
                if (trial.count >= n) { winner = trial; upper = trial.side; }
                else lower = (upper+lower)/2;
            }
            std::cout << std::setprecision(17) << winner.count << ' ' << winner.side
                << ' ' << winner.phase << ' ' << winner.bl << ' ' << winner.tr
                << ' ' << winner.br << ' ' << winner.tl << '\n';
            n = winner.count+1;
            lower = winner.side;
        }
        std::cout.flush();
    }
}
