// Piecewise smooth overlap and wall penalties for a fixed enclosing side.
#include <cmath>
#include <vector>

namespace {
struct Vec {
    double x, y;
    Vec operator-(Vec b) const { return {x - b.x, y - b.y}; }
    Vec operator*(double s) const { return {x * s, y * s}; }
    Vec normal() const { return {-y, x}; }
    double dot(Vec b) const { return x * b.x + y * b.y; }
};
double sign(double x) { return (x > 0) - (x < 0); }

struct Separation {
    double gap = -2.;
    Vec normal{};
    double first_angle = 0.;
    double second_angle = 0.;
};

void check_face(Vec axis, Vec other, Vec displacement, bool from_first, Separation& best) {
    const double pr = displacement.dot(axis);
    const double c = axis.dot(other), s = axis.dot(other.normal());
    const double gap = std::abs(pr) - .5 * (1. + std::abs(c) + std::abs(s));
    if (gap <= best.gap) return;
    const double radius_delta = .5 * (sign(c) * s - sign(s) * c);
    const double owner_delta = sign(pr) * displacement.dot(axis.normal()) + radius_delta;
    best = {gap, axis * sign(pr), from_first ? owner_delta : -radius_delta,
        from_first ? -radius_delta : owner_delta};
}
}

extern "C" double pressure_loss(int n, double side, const double* x, double* gradient) {
    std::vector<Vec> axes(n);
    double loss = 0.;
    for (int i = 0; i < n; ++i) {
        const int p = 3*i;
        const auto [c,s] = axes[i] = {std::cos(x[p+2]), std::sin(x[p+2])};
        const double half = .5 * (std::abs(c) + std::abs(s));
        const double dhalf = .5 * (-sign(c) * s + sign(s) * c);
        gradient[p] = gradient[p+1] = gradient[p+2] = 0.;
        for (int d = 0; d < 2; ++d) {
            const double low = half - x[p+d];
            const double high = x[p+d] + half - side;
            if (low > 0.) {
                loss += low * low;
                gradient[p+d] -= 2. * low;
                gradient[p+2] += 2. * low * dhalf;
            }
            if (high > 0.) {
                loss += high * high;
                gradient[p+d] += 2. * high;
                gradient[p+2] += 2. * high * dhalf;
            }
        }
    }
    for (int i = 0; i < n; ++i) {
        for (int j = i+1; j < n; ++j) {
            const Vec d{x[3*j] - x[3*i], x[3*j+1] - x[3*i+1]};
            if (d.dot(d) >= 2.) continue;
            Separation best;
            check_face(axes[i], axes[j], d, true, best);
            check_face(axes[i].normal(), axes[j], d, true, best);
            check_face(axes[j], axes[i], d, false, best);
            check_face(axes[j].normal(), axes[i], d, false, best);
            if (best.gap >= 0.) continue;
            loss += best.gap * best.gap;
            const double m = 2. * best.gap;
            gradient[3*i] -= m * best.normal.x;
            gradient[3*i+1] -= m * best.normal.y;
            gradient[3*j] += m * best.normal.x;
            gradient[3*j+1] += m * best.normal.y;
            gradient[3*i+2] += m * best.first_angle;
            gradient[3*j+2] += m * best.second_angle;
        }
    }
    return loss;
}
