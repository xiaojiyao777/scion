from __future__ import annotations

from ..models import Route, Solution

_EPS = 1e-9


def _prev(route: Route, pos: int, depot: int) -> int:
    return depot if pos == 0 else route.customers[pos - 1]


def _next(route: Route, pos: int, depot: int) -> int:
    return depot if pos == len(route.customers) - 1 else route.customers[pos + 1]


# ---------------------------------------------------------------------------
# Intra-route: 2-opt
# ---------------------------------------------------------------------------

def two_opt_intra(solution: Solution) -> bool:
    """Reverse a segment within a single route (repeated first improvement)."""
    inst = solution.instance
    depot = inst.depot
    improved = False

    for route in solution.routes:
        custs = route.customers
        n = len(custs)
        if n < 2:
            continue
        found = True
        while found:
            found = False
            for i in range(n - 1):
                for j in range(i + 1, n):
                    prev_i = depot if i == 0 else custs[i - 1]
                    next_j = depot if j == n - 1 else custs[j + 1]
                    delta = (inst.dist(prev_i, custs[j]) + inst.dist(custs[i], next_j)
                             - inst.dist(prev_i, custs[i]) - inst.dist(custs[j], next_j))
                    if delta < -_EPS:
                        custs[i:j + 1] = custs[i:j + 1][::-1]
                        route._recalculate()
                        solution.total_cost += delta
                        solution._rebuild_index()
                        improved = True
                        found = True
                        break
                if found:
                    break
    return improved


# ---------------------------------------------------------------------------
# Inter-route: relocate (move one customer to any other position)
# ---------------------------------------------------------------------------

def relocate(solution: Solution) -> bool:
    """Move one customer to a better position (inter-route only for simplicity)."""
    inst = solution.instance
    depot = inst.depot
    routes = solution.routes
    n_routes = len(routes)
    improved = False

    found = True
    while found:
        found = False
        for ri in range(n_routes):
            r_from = routes[ri]
            if len(r_from) == 0:
                continue
            for pos in range(len(r_from)):
                c = r_from.customers[pos]
                prev_c = _prev(r_from, pos, depot)
                next_c = _next(r_from, pos, depot)
                # Cost saved by removing c from r_from
                save = (inst.dist(prev_c, c) + inst.dist(c, next_c)
                        - inst.dist(prev_c, next_c))

                best_gain = _EPS
                best_rj = -1
                best_ins = -1

                for rj in range(n_routes):
                    if rj == ri:
                        continue  # intra handled by 2-opt / or-opt
                    r_to = routes[rj]
                    if not r_to.can_insert(c):
                        continue
                    nj = len(r_to)
                    for ins in range(nj + 1):
                        p = depot if ins == 0 else r_to.customers[ins - 1]
                        n_ = depot if ins == nj else r_to.customers[ins]
                        cost_ins = inst.dist(p, c) + inst.dist(c, n_) - inst.dist(p, n_)
                        gain = save - cost_ins
                        if gain > best_gain:
                            best_gain = gain
                            best_rj = rj
                            best_ins = ins

                if best_rj >= 0:
                    r_from.remove(pos)
                    routes[best_rj].insert(c, best_ins)
                    solution.total_cost -= best_gain
                    solution._rebuild_index()
                    improved = True
                    found = True
                    break
            if found:
                break
    return improved


# ---------------------------------------------------------------------------
# Inter-route: swap (exchange one customer between two routes)
# ---------------------------------------------------------------------------

def swap(solution: Solution) -> bool:
    """Exchange one customer between two different routes."""
    inst = solution.instance
    depot = inst.depot
    routes = solution.routes
    n_routes = len(routes)
    improved = False

    found = True
    while found:
        found = False
        for ri in range(n_routes - 1):
            r_i = routes[ri]
            for rj in range(ri + 1, n_routes):
                r_j = routes[rj]
                for pi in range(len(r_i)):
                    ci = r_i.customers[pi]
                    prev_i = _prev(r_i, pi, depot)
                    next_i = _next(r_i, pi, depot)
                    for pj in range(len(r_j)):
                        cj = r_j.customers[pj]
                        # Capacity check
                        new_load_i = r_i.load - int(inst.demands[ci]) + int(inst.demands[cj])
                        new_load_j = r_j.load - int(inst.demands[cj]) + int(inst.demands[ci])
                        if new_load_i > inst.capacity or new_load_j > inst.capacity:
                            continue
                        prev_j = _prev(r_j, pj, depot)
                        next_j = _next(r_j, pj, depot)
                        # Correct delta: replace ci with cj in r_i, replace cj with ci in r_j
                        delta_i = (inst.dist(prev_i, cj) + inst.dist(cj, next_i)
                                   - inst.dist(prev_i, ci) - inst.dist(ci, next_i))
                        delta_j = (inst.dist(prev_j, ci) + inst.dist(ci, next_j)
                                   - inst.dist(prev_j, cj) - inst.dist(cj, next_j))
                        if delta_i + delta_j < -_EPS:
                            r_i.customers[pi] = cj
                            r_j.customers[pj] = ci
                            r_i.load = new_load_i
                            r_j.load = new_load_j
                            r_i.cost += delta_i
                            r_j.cost += delta_j
                            solution.total_cost += delta_i + delta_j
                            solution._rebuild_index()
                            improved = True
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return improved


# ---------------------------------------------------------------------------
# Or-opt: move a segment of L customers between routes
# ---------------------------------------------------------------------------

def or_opt(solution: Solution, seg_len: int = 1) -> bool:
    """Move a segment of seg_len consecutive customers to a better inter-route position."""
    inst = solution.instance
    depot = inst.depot
    routes = solution.routes
    n_routes = len(routes)
    improved = False

    found = True
    while found:
        found = False
        for ri in range(n_routes):
            r_from = routes[ri]
            ni = len(r_from)
            if ni < seg_len:
                continue

            for pos in range(ni - seg_len + 1):
                seg = r_from.customers[pos:pos + seg_len]
                prev_seg = depot if pos == 0 else r_from.customers[pos - 1]
                next_seg = depot if pos + seg_len == ni else r_from.customers[pos + seg_len]

                seg_internal = sum(inst.dist(seg[k], seg[k + 1]) for k in range(seg_len - 1))
                # Cost saved by removing segment from r_from
                save = (inst.dist(prev_seg, seg[0]) + seg_internal + inst.dist(seg[-1], next_seg)
                        - inst.dist(prev_seg, next_seg))
                seg_demand = sum(int(inst.demands[c]) for c in seg)

                best_gain = _EPS
                best_rj = -1
                best_ins = -1
                best_rev = False

                for rj in range(n_routes):
                    if rj == ri:
                        continue  # skip intra-route (handled by 2-opt)
                    r_to = routes[rj]
                    if r_to.load + seg_demand > inst.capacity:
                        continue
                    nj = len(r_to)
                    for ins in range(nj + 1):
                        p = depot if ins == 0 else r_to.customers[ins - 1]
                        n_ = depot if ins == nj else r_to.customers[ins]
                        for rev in ([False, True] if seg_len > 1 else [False]):
                            s0, s_end = (seg[-1], seg[0]) if rev else (seg[0], seg[-1])
                            cost_ins = inst.dist(p, s0) + seg_internal + inst.dist(s_end, n_) - inst.dist(p, n_)
                            gain = save - cost_ins
                            if gain > best_gain:
                                best_gain = gain
                                best_rj = rj
                                best_ins = ins
                                best_rev = rev

                if best_rj >= 0:
                    seg_copy = list(reversed(seg)) if best_rev else list(seg)
                    for _ in range(seg_len):
                        r_from.remove(pos)
                    for k, c in enumerate(seg_copy):
                        routes[best_rj].insert(c, best_ins + k)
                    solution.total_cost -= best_gain
                    solution._rebuild_index()
                    improved = True
                    found = True
                    break
            if found:
                break
    return improved


def or_opt_1(solution: Solution) -> bool:
    return or_opt(solution, 1)


def or_opt_2(solution: Solution) -> bool:
    return or_opt(solution, 2)


def or_opt_3(solution: Solution) -> bool:
    return or_opt(solution, 3)


# ---------------------------------------------------------------------------
# Inter-route: 2-opt* (reconnect route tails)
# ---------------------------------------------------------------------------

def two_opt_star(solution: Solution) -> bool:
    """Reconnect tails of two routes."""
    inst = solution.instance
    depot = inst.depot
    routes = solution.routes
    n_routes = len(routes)
    improved = False

    found = True
    while found:
        found = False
        for ri in range(n_routes - 1):
            r_i = routes[ri]
            ni = len(r_i)
            custs_i = r_i.customers
            for rj in range(ri + 1, n_routes):
                r_j = routes[rj]
                nj = len(r_j)
                custs_j = r_j.customers

                # Precompute prefix loads for both routes
                prefix_i = [0] * (ni + 1)
                for k in range(ni):
                    prefix_i[k + 1] = prefix_i[k] + int(inst.demands[custs_i[k]])
                prefix_j = [0] * (nj + 1)
                for k in range(nj):
                    prefix_j[k + 1] = prefix_j[k] + int(inst.demands[custs_j[k]])

                tail_i = [prefix_i[ni] - prefix_i[k] for k in range(ni + 1)]
                tail_j = [prefix_j[nj] - prefix_j[k] for k in range(nj + 1)]

                for p1 in range(ni + 1):
                    a1 = depot if p1 == 0 else custs_i[p1 - 1]
                    b1 = depot if p1 == ni else custs_i[p1]
                    for p2 in range(nj + 1):
                        # New route i: custs_i[:p1] + custs_j[p2:]
                        # New route j: custs_j[:p2] + custs_i[p1:]
                        if prefix_i[p1] + tail_j[p2] > inst.capacity:
                            continue
                        if prefix_j[p2] + tail_i[p1] > inst.capacity:
                            continue
                        a2 = depot if p2 == 0 else custs_j[p2 - 1]
                        b2 = depot if p2 == nj else custs_j[p2]
                        delta = (inst.dist(a1, b2) + inst.dist(a2, b1)
                                 - inst.dist(a1, b1) - inst.dist(a2, b2))
                        if delta < -_EPS:
                            new_i = custs_i[:p1] + custs_j[p2:]
                            new_j = custs_j[:p2] + custs_i[p1:]
                            routes[ri] = Route(inst, new_i)
                            routes[rj] = Route(inst, new_j)
                            solution.total_cost += delta
                            solution._rebuild_index()
                            improved = True
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return improved
