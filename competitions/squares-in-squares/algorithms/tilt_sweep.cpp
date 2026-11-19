// Enumerate tilted strip witnesses. Output: k L capacity angle(deg) phase first last.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <vector>

namespace {
constexpr double pi = 3.14159265358979323846;
constexpr double eps = 1e-10;
constexpr int steps = 64;

struct Witness {
    int capacity, first, last;
    double degrees, phase;
};

// A near-integer trial finds tilts that only just break the integer grid.
double trial_side(int k, int index) {
    return k + (index == steps ? 1.0 - 1e-6 : double(index) / steps);
}

int corner_count(const std::vector<double>& distances, double margin) {
    return std::upper_bound(distances.begin(), distances.end(), margin + eps) - distances.begin();
}

void scan_angle(int k, double degrees, std::vector<Witness>& best) {
    const double theta = degrees * pi / 180;
    const double s = std::sin(theta), c = std::cos(theta), g = s*c;
    // Farthest vertex of an axis-aligned tile measured from its own corner.
    std::vector<double> distances, phases{0};
    for (int i = 1; i <= k; ++i) {
        for (int j = 1; j <= k; ++j) {
            distances.push_back(i*s + j*c);
            phases.push_back(std::fmod(0.5 + distances.back(), 1.0));
        }
    }
    for (int length = 1; length <= std::ceil((k + 1)/c); ++length)
        phases.push_back(std::fmod(0.5 + length*g, 1.0));
    std::sort(distances.begin(), distances.end());
    std::sort(phases.begin(), phases.end());

    const int max_row = std::ceil((s + c)*(k + 1));
    std::vector<int> lower_count(max_row + 1), lower_span(max_row + 1);
    double previous = -1;
    for (double phase : phases) {
        if (phase - previous < eps) continue;
        previous = phase;
        for (int j = 0; j <= max_row; ++j) {
            double a = phase + j - 0.5;
            lower_count[j] = corner_count(distances, a);
            lower_span[j] = std::floor(a/g + eps);
        }
        for (int index = 1; index <= steps; ++index) {
            const double side = trial_side(k, index), width = side*(s + c);
            const int max_length = std::floor((side - s)/c + eps);
            int prefix = 0, best_start = 0, best_offset = -100000;
            const int first = std::ceil(0.5 - phase - eps);
            const int last = std::floor(width - phase - 0.5 + eps);
            for (int j = first; j <= last; ++j) {
                // With a fixed last row, all earlier starts share the same tail.
                if (lower_count[j] - prefix > best_offset) {
                    best_offset = lower_count[j] - prefix;
                    best_start = j;
                }
                const double b = width - phase - j - 0.5;
                const int upper_span = std::floor(b/g + eps);
                prefix += std::min({lower_span[j], max_length, upper_span});
                const int capacity = best_offset + prefix + corner_count(distances, b);
                if (capacity > best[index].capacity)
                    best[index] = {capacity, best_start, j, degrees, phase};
            }
        }
    }
}
} // namespace

int main() {
    std::vector<double> angles;
    // Include commensurate slopes as well as intermediate half-degree angles.
    for (int i = 1; i <= 90; ++i) angles.push_back(i * 0.5);
    for (int b = 2; b <= 16; ++b) {
        for (int a = 1; a < b; ++a)
            angles.push_back(std::atan(double(a)/b)*180/pi);
    }
    std::sort(angles.begin(), angles.end());
    std::cout << std::setprecision(17);
    for (int k = 2; k <= 31; ++k) {
        std::vector<Witness> best(steps + 1, {k*k, 0, 0, 0, 0});
        double previous = -1;
        for (double degrees : angles) {
            if (degrees - previous < eps) continue;
            scan_angle(k, degrees, best);
            previous = degrees;
        }
        for (int index = 1; index <= steps; ++index) {
            const auto& w = best[index];
            if (w.capacity <= k*k) continue;
            std::cout << k << ' ' << trial_side(k, index) << ' ' << w.capacity << ' '
                      << w.degrees << ' ' << w.phase << ' ' << w.first << ' ' << w.last << '\n';
        }
        std::cout.flush();
    }
}
