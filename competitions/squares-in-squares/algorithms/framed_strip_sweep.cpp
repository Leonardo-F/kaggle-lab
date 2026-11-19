// A unit grid rim around a 45-degree strip in a rectangular interior.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <vector>

namespace {
const double root_two = std::sqrt(2.0);
constexpr double eps = 1e-11;
constexpr int max_n = 1000;
struct Witness {
    int capacity = 0, rim = 0, rows = 0;
    double lower = 0;
};

int triangle(int d) { return d > 0 ? d*(d+1)/2 : 0; }

// Integer pairs 1 <= i <= w, 1 <= j <= h, i+j <= depth.
int corner(int depth, int w, int h) {
    return triangle(depth-1) - triangle(depth-w-1) - triangle(depth-h-1)
        + triangle(depth-w-h-1);
}

// Sum min(cap, base+2*j) over count terms.
int ramp(int count, int base, int cap) {
    const int rising = std::min(count, std::max(0, (cap-base+1)/2));
    return rising*(base+rising-1) + (count-rising)*cap;
}

Witness best_at(double side, int k, const std::vector<double>& margins) {
    Witness best;
    for (int rim = 0; rim < k; ++rim) {
        const int w = k-rim;
        const int cap = std::floor(root_two*(side-rim)-1+eps);
        const double span = (2*side-rim)/root_two;
        for (double a : margins) {
            if (a+1 > span+eps) break;
            const int first = std::floor(2*a+eps);
            const int fixed = rim*k + corner(std::floor(root_two*a+eps),w,k);
            const int max_rows = std::floor(span-a+eps);
            for (int rows=1; rows<=max_rows; ++rows) {
                const double b = span-a-rows;
                const int last = std::floor(2*b+eps);
                const int crossover = last-first + 2*(rows-1);
                const int split = crossover < 0 ? 0 : std::min(rows, crossover/4+1);
                const int count = fixed + corner(std::floor(root_two*b+eps),w,k)
                    + ramp(split,first,cap) + ramp(rows-split,last,cap);
                if (count > best.capacity) best = {count,rim,rows,a};
            }
        }
    }
    return best;
}
}

int main() {
    std::cout << std::setprecision(17);
    for (int k=2; k*k<max_n; ++k) {
        std::vector<double> margins;
        for (int i=0; i<=4*(k+1); ++i) {
            margins.push_back(i/2.0);
            margins.push_back(i/root_two);
        }
        std::sort(margins.begin(),margins.end());
        margins.erase(std::unique(margins.begin(),margins.end()),margins.end());
        std::map<double,Witness> cache;
        auto evaluate = [&](double side) {
            auto it = cache.find(side);
            if (it != cache.end()) return it->second;
            return cache.emplace(side,best_at(side,k,margins)).first->second;
        };
        const double ceiling = k+1-1e-8;
        const int limit = std::min(max_n,evaluate(ceiling).capacity);
        for (int n=k*k+1; n<=limit; ++n) {
            double lo=k, hi=ceiling;
            for (int iter=0; iter<31; ++iter) {
                const double mid = (lo+hi)/2;
                if (evaluate(mid).capacity >= n) hi=mid;
                else lo=mid;
            }
            const Witness witness=evaluate(hi);
            std::cout << n << ' ' << hi << ' ' << witness.capacity << ' '
                      << witness.rim << ' ' << witness.rows << ' ' << witness.lower << '\n';
        }
    }
}
