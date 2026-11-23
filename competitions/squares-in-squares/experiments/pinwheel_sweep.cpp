// Search four rectangular edge bands around an integer grid, in cyclic order.
#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numbers>
#include <string>
#include <vector>

namespace {
constexpr int units = 2000;  // Fixed-point representation of candidate strip widths.
constexpr double eps = 1e-10;
int count_floor(double x) { return static_cast<int>(std::floor(x + eps)); }

struct Trig {
    double s, c;
};
const auto angles = [] {
    std::vector<Trig> result;
    for (double theta = 10; theta <= 80; theta += .5) {
        const double radians = theta * std::numbers::pi / 180;
        result.push_back({std::sin(radians), std::cos(radians)});
    }
    return result;
}();

int rectangle(double width, double height) {
    if (height < 1 || width < 1) return 0;
    int best = count_floor(width) * count_floor(height);
    if (best == count_floor(width * height)) return best;
    std::vector<double> corners;
    corners.reserve(best);
    for (const auto& [s, c] : angles) {
        const int cap = std::min(count_floor((width - s) / c), count_floor((height - c) / s));
        if (cap <= 0) continue;
        const double span = width * s + height * c, product = s * c;
        corners.clear();
        for (int x = 1; x <= count_floor(width); ++x)
            for (int y = 1; y <= count_floor(height); ++y) {
                const double d = x * s + y * c;
                if (d < span - 1 + eps) corners.push_back(d);
            }
        std::sort(corners.begin(), corners.end());
        for (int phase = 0; phase < 16; ++phase) {
            int left = 0, right = corners.size(), sum = 0, prefix = 0;
            for (double lower = phase / 16.; lower <= span - 1 + eps; ++lower) {
                const double upper = span - 1 - lower;
                while (left < int(corners.size()) && corners[left] <= lower + eps) ++left;
                while (right > 0 && corners[right - 1] > upper + eps) --right;
                prefix = std::max(prefix, left - sum);
                sum += std::min({cap, count_floor(lower / product), count_floor(upper / product)});
                best = std::max(best, prefix + sum + right);
            }
        }
        if (best == count_floor(width * height)) break;
    }
    return best;
}

void search(int k, int fraction, int& best) {
    const int side = k * units + fraction;
    for (int x = 0; x < 3; ++x) {
        for (int y = x; y < 3; ++y) {
            const std::array<int, 4> extra{fraction * x / 2, fraction * y / 2,
                fraction - fraction * x / 2, fraction - fraction * y / 2};
            // Each of the four bands ends where the next one begins.
            std::array<int, 4> widths{};
            const int max_width = std::min(k, 10);
            std::array<std::array<std::array<int, 11>, 11>, 4> caps{};
            for (int i = 0; i < 4; ++i) {
                for (int w = 0; w <= max_width; ++w) {
                    for (int next = 0; next <= max_width; ++next) {
                        const double a = double(side - next * units - extra[(i + 1) % 4]) / units;
                        const double b = double(w * units + extra[i]) / units;
                        caps[i][w][next] = rectangle(std::max(a,b), std::min(a,b));
                    }
                }
            }
            for (int b = 0; b <= max_width; ++b)
                for (int r = 0; r <= max_width; ++r)
                    for (int t = 0; t <= std::min(max_width, k-b); ++t)
                        for (int l = 0; l <= std::min(max_width, k-r); ++l) {
                            const int n = caps[0][b][r] + caps[1][r][t] + caps[2][t][l]
                                + caps[3][l][b] + (k-b-t) * (k-r-l);
                            if (n <= best) continue;
                            best = n;
                            widths = {b, r, t, l};
                            std::cout << k << ' ' << fraction / double(units) << ' ' << n;
                            for (int i = 0; i < 4; ++i)
                                std::cout << ' ' << (widths[i] + extra[i] / double(units));
                            std::cout << '\n';
                        }
        }
    }
}
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int k = std::stoi(argv[1]);
    if (k < 2 || k > 31) return 2;
    std::cout << std::setprecision(12);
    int best = k*k;
    for (int fraction : {1100, 1250, 1400, 1500, 1600, 1700, 1800, 1860, 1920, 1960, 1990, 1998}) {
        search(k, fraction, best);
        std::cout.flush();
    }
}
