"""
Direct CNF encoding of Exact ell-clique-minimal Existence, solved with the
standalone CaDiCaL binary and certified with LRAT proofs.

The clauses follow the CNF lemmas of the thesis exactly.

Installation:
    pip install python-sat[pblib,aiger]
    pip install networkx

    # download and build CaDiCaL
    git clone --depth 1 https://github.com/arminbiere/cadical.git
    cd cadical && ./configure && make

    # download and build 
    git clone --depth 1 https://github.com/tanyongkiam/cake_lpr.git
    cd cake_lpr && sha256sum -c cake_lpr.sha256
    cd cake_lpr && make cake_lpr

Run:
    python sat.py --help
    python sat.py -l 6
"""
import argparse
import math
import os
import signal
import subprocess
import sys
import time

import pysat
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Cadical300

ABORT = False
CURRENT_PROCESS = None

TIME_MODEL_BUILDING = 0.0
TIME_SAT = 0.0
TIME_VERIFY = 0.0


def _on_sigint(signum, frame):
    global ABORT
    ABORT = True
    print("\nInterrupted: stopping...", flush=True)
    if CURRENT_PROCESS is not None:
        try:
            CURRENT_PROCESS.terminate()
        except Exception:
            pass


signal.signal(signal.SIGINT, _on_sigint)

#######################################################################################
# the SAT encoding (model)

# lexicographic ordering of two equal-length boolean vectors, a <=_lex b
def lexicographic_ordering_less_or_equal(pool, clauses, a, b, tag):
    """Clauses of Definition 'Lexicographically ordering boolean vectors'.
    prefixEqual[i] <=> (a_0..a_i) == (b_0..b_i), for i in [0, k-2].
    """
    k = len(a)
    if k == 0:
        return
    if k == 1:
        clauses.append([-a[0], b[0]])  # a_0 => b_0
        return

    prefix_equal = [pool.id(("prefixEqual", tag, i)) for i in range(k - 1)]

    # base case value: a_0 => b_0
    clauses.append([-a[0], b[0]])
    # base case prefix: prefixEqual[0] <=> (a_0 <=> b_0)
    clauses += [
        [-prefix_equal[0], -a[0], b[0]],
        [-prefix_equal[0], a[0], -b[0]],
        [prefix_equal[0], -a[0], -b[0]],
        [prefix_equal[0], a[0], b[0]],
    ]

    # iterative prefix: prefixEqual[i] <=> prefixEqual[i-1] & (a_i <=> b_i)
    for i in range(1, k - 1):
        clauses += [
            [-prefix_equal[i], prefix_equal[i - 1]],
            [-prefix_equal[i], -a[i], b[i]],
            [-prefix_equal[i], a[i], -b[i]],
            [prefix_equal[i], -prefix_equal[i - 1], -a[i], -b[i]],
            [prefix_equal[i], -prefix_equal[i - 1], a[i], b[i]],
        ]

    # iterative value: prefixEqual[i] => (a_{i+1} => b_{i+1}) for ALL i in [0,k-2]
    # NOTE: the index must start at 0 not at 1
    for i in range(0, k - 1):
        clauses.append([-prefix_equal[i], -a[i + 1], b[i + 1]])


# the model
def encode_model(ell, kappa, n, enc=EncType.seqcounter, symmetry=True):
    assert kappa >= ell, "kappa must be >= ell"
    V, CG = range(n), range(kappa)

    # ID pool that given a key returns the ID (integer) of the variable
    pool = IDPool()

    # C[v][i] <=> vertex v is in clique i
    C = {(v, i): pool.id(("C",v,i)) for v in V for i in CG}

    # S[v][i][j] <=> v in C_i \ C_j
    S = {
        (v, i, j): pool.id(("S", v, i, j))
        for v in V for i in CG for j in CG
        if i != j
    }

    # DiffSingleton[v][i][j] <=> C_i \ C_j = {v}
    DiffSingleton = {
        (v, i, j): pool.id(("DiffSingleton", v, i, j))
        for v in V for i in CG for j in CG
        if i != j
    }

    # D[v][i] = there exists j != i such that C_i \ C_j = {v}
    D = {(v, i): pool.id(("D", v, i)) for v in V for i in CG}

    # vInside[i,j,k, v] <=> v \in (C_i \cap C_j) \cup (C_i \cap C_k) \cup (C_j \cap C_k)
    vInside = {
        (i,j,k,v): pool.id(("vInside", i, j, k, v))
        for i in CG for j in CG for k in CG for v in V
        if i < j and j < k
    }

    # isSuperset[i,j,k, d] <=> C_d \supseteq (C_i \cap C_j) \cup (C_i \cap C_k) \cup (C_j \cap C_k)
    isSuperset = {
        (i,j,k,d): pool.id(("isSuperset", i, j, k, d))
        for i in CG for j in CG for k in CG for d in CG
        if i < j and j < k
    }

    # list of clauses following the DIMACS format
    # (list of list of variable IDs, negative if negated)
    clauses = []

    # S[v,i,j]
    for v in V:
        for i in CG:
            for j in CG:
                if i == j:
                    continue
                clauses += [
                    # =>
                    [-S[v, i,j], C[v,i]],
                    [-S[v, i,j], -C[v,j]],
                    # <=
                    [S[v, i,j], -C[v,i], C[v,j]]
                ]

    # DiffSingleton[v,i,j]
    for v in V:
        for i in CG:
            for j in CG:
                if i == j:
                    continue
                # =>
                clauses.append([-DiffSingleton[v, i,j], S[v, i,j]])
                for w in V:
                    if w != v:
                        clauses.append([-DiffSingleton[v, i,j], -S[w, i,j]])

                # <=
                clauses.append([DiffSingleton[v, i,j], -S[v, i,j]] + [S[w, i,j] for w in V if w != v])

    # D[v, i]
    for v in V:
        for i in CG:
            witnesses = [DiffSingleton[v, i,j] for j in CG if j != i]
            # =>
            clauses.append([-D[v, i]] + witnesses)
            # <=
            for w in witnesses:
                clauses.append([D[v, i], -w])

    # Sperner + cliques non-empty
    for i in CG:
        # added condition: every clique is non-empty
        clauses.append([C[v,i] for v in V])

        for j in CG:
            if i != j:
                clauses.append([S[v, i,j] for v in V])

    # conformality: vInside, isSuperset, conformality condition
    for i in CG:
        for j in CG:
            if j <= i:
                continue
            for k in CG:
                if k <= j:
                    continue
                # i < j < k

                # vInside
                for v in V:
                    vIn = vInside[i,j,k, v]
                    Ci, Cj, Ck = C[v,i], C[v,j], C[v, k]
                    clauses += [
                        # =>
                        [-vIn, Ci, Cj], [-vIn, Ci, Ck], [-vIn, Cj, Ck],
                        # <=
                        [vIn, -Ci, -Cj], [vIn, -Ci, -Ck], [vIn, -Cj, -Ck],
                    ]

                # isSuperset
                for d in CG:
                    for v in V:
                        clauses.append([-isSuperset[i,j,k, d], -vInside[i,j,k, v], C[v, d]])

                # conformality
                clauses.append([isSuperset[i,j,k, d] for d in CG])

    # condition for ell-clique-minimality
    cardinality_clauses = 0
    for v in V:
        cnf = CardEnc.atleast(lits=[D[v, i] for i in CG], bound=1+kappa-ell,
                              vpool=pool, encoding=enc)
        clauses += cnf.clauses
        cardinality_clauses += len(cnf.clauses)

    # lexicographic ordering
    if symmetry:
        for v in range(n - 1): # rows: clique memberships of v
            lexicographic_ordering_less_or_equal(
                pool, clauses, [C[v,i] for i in CG], [C[v + 1, i] for i in CG], f"row{v}")
        for i in range(kappa - 1): # columns: elements of C_i
            lexicographic_ordering_less_or_equal(
                pool, clauses, [C[v,i] for v in V], [C[v, i + 1] for v in V], f"col{i}")

    return clauses, pool.top, cardinality_clauses, C

#######################################################################################
# verification of found solutions: condition for ell-clique-minimality

# calculate maximal cliques using bron-kerbosch
def _maximal_cliques(verts, adj):
    verts = set(verts)
    sub = {v: (adj[v] & verts) for v in verts}
    out = []

    # bron-kerbosch
    def bronKerbosch(R, P, X):
        if not P and not X:
            out.append(frozenset(R))
            return
        piv = max(P | X, key=lambda z: len(sub[z] & P))
        for z in list(P - sub[piv]):
            bronKerbosch(R | {z}, P & sub[z], X & sub[z])
            P = P - {z}
            X = X | {z}

    bronKerbosch(set(), set(verts), set())
    return out

# verify the solution (#maximal cliques = kappa >= ell, for every vertex G-x has < ell maximal cliques)
def verify_solution(n, ell, kappa, rows):
    adj = {v: set() for v in range(n)}
    for R in rows:
        for a in R:
            for b in R:
                if a != b:
                    adj[a].add(b)
    cl = _maximal_cliques(range(n), adj)
    if len(cl) != kappa:
        return False, f"graph has {len(cl)} maximal cliques, expected {kappa}"
    if {frozenset(x) for x in rows} != set(cl):
        return False, "rows are not the maximal cliques of the derived graph"
    for v in range(n):
        if len(_maximal_cliques(set(range(n)) - {v}, adj)) > ell - 1:
            return False, f"G-{v} still has more than {ell-1} maximal cliques"
    return True, "ell-clique-minimal, verified from the definition"


#######################################################################################
# solver function calling the SAT solver (CaDiCaL) and LRAT verifier (cake_lpr)

def get_proof_name(ell, kappa, n):
    return f"ell-{ell}_kappa-{kappa}_n-{n}"


def print_solution(rows):
    for i, R in enumerate(rows):
        print(f"  C_{i} = {R}")


def human_readable_bytes(k):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if k < 1024 or unit == "TiB":
            return f"{k:.1f} {unit}"
        k /= 1024


# solve one instance with the standalone CaDiCaL binary, producing an LRAT proof
def solve_instance(ell, kappa, n=0, enc=EncType.seqcounter,
                   cadical="./cadical/build/cadical", checker="./cake_lpr/cake_lpr",
                   proof_location="./sat-proofs", delete_proof=False, text_lrat=False,
                   disable_proof=False, checker_args=[]):
    """returns True iff a graph was found (and verified)

    PySAT cannot emit LRAT, so the formula is written to DIMACS and the
    standalone CaDiCaL binary is called.
    """
    global CURRENT_PROCESS, TIME_MODEL_BUILDING, TIME_SAT, TIME_VERIFY, ABORT
    assert kappa >= ell, "kappa must be >= ell"
    if n <= 0:
        n = 2 * (ell - 1) + 1

    os.makedirs(proof_location, exist_ok=True)
    tag = os.path.join(proof_location, get_proof_name(ell, kappa, n))

    # build the model
    t0 = time.perf_counter()
    clauses, nvars, ncard, cmap = encode_model(ell, kappa, n, enc=enc)
    CNF(from_clauses=clauses).to_file(tag + ".cnf")
    t_build = time.perf_counter() - t0
    TIME_MODEL_BUILDING += t_build

    print(f"Starting CaDiCaL for ell={ell}, kappa={kappa}, n={n}: "
          f"{nvars} variables, {len(clauses)} clauses "
          f"({ncard} from the cardinality encoding), built in {t_build:.3f}s")

    # run the cadical binary
    cmd = [cadical]
    if not disable_proof:  # do proof logging in the LRAT format
        cmd.append("--lrat")
    if text_lrat:  # LRAT in text format
        cmd.append("--binary=false")
    cmd += [tag + ".cnf", tag + ".lrat"]

    t0 = time.perf_counter()
    CURRENT_PROCESS = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, universal_newlines=True)
    stdout, _ = CURRENT_PROCESS.communicate()
    CURRENT_PROCESS = None
    t_sat = time.perf_counter() - t0
    TIME_SAT += t_sat
    verdict = next((l for l in stdout.splitlines() if l.startswith("s ")), "s UNKNOWN")

    # UNSAT: verify the LRAT proof
    if verdict.startswith("s UNSATISFIABLE"):
        if not disable_proof:
            size = os.path.getsize(tag + ".lrat")
            print(f"  UNSAT (proven) in {t_sat:.3f}s, LRAT proof {human_readable_bytes(size)}")
            t0 = time.perf_counter()
            c = subprocess.run([checker] + list(checker_args) + [tag + ".cnf", tag + ".lrat"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            t_ver = time.perf_counter() - t0
            TIME_VERIFY += t_ver
            stdout, stderr = c.stdout, c.stderr

            # absence of VERIFIED counts as failure: a checker that parsed nothing
            # still prints plausible-looking statistics
            ok = "s VERIFIED" in c.stdout
            print(f"  LRAT check ({os.path.basename(checker)}): "
                f"{'VERIFIED' if ok else 'FAILED'} in {t_ver:.3f}s")
            if len(stderr)>0:
                print(f"Checker {checker} stderr: {stderr}")
            if ok and delete_proof:
                os.remove(tag + ".lrat")
                print(f"  deleted {tag}.lrat and freed {human_readable_bytes(size)} "
                    f" (kept the DIMACS file)")
            if not ok:
                ABORT = True
        else:
            print(f"  UNSAT (proven) in {t_sat:.3f}s, not verified by LRAT.")
        return False

    # SAT
    if verdict.startswith("s SATISFIABLE"):
        pos = {int(x) for line in stdout.splitlines() if line.startswith("v ")
               for x in line[2:].split() if int(x) > 0}
        rows = [sorted(v for v in range(n) if cmap[(v, i)] in pos) for i in range(kappa)]
        print(f"  SAT in {t_sat:.3f}s")
        print_solution(rows)
        t0 = time.perf_counter()
        ok, why = verify_solution(n, ell, kappa, rows)
        TIME_VERIFY += time.perf_counter() - t0
        print(f"  independent verification: {'OK' if ok else 'FAILED'} ({why})")
        if os.path.exists(tag + ".lrat"):
            os.remove(tag + ".lrat")        # a SAT run leaves an incomplete proof
        if not ok:
            ABORT = True
        return ok

    # solver did not finish (did not return SAT/UNSAT)
    print(f"  {verdict} after {t_sat:.3f}s - NOT a proof")
    if os.path.exists(tag + ".lrat"):  # remove incomplete LRAT
        os.remove(tag + ".lrat")
    ABORT = True
    return False

#######################################################################################
# enumerate SAT solutions by adding blocking clauses
# (using PySat so we do not have to restart the solver from scratch for every solution)

def to_graph6(rows, n):
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for R in rows:
        G.add_edges_from((a, b) for a in R for b in R if a < b)
    return nx.to_graph6_bytes(G, header=False).decode().strip()

# enumerate instances with our model + blocking clauses
def enumerate_instance(ell, kappa, n, enc=EncType.seqcounter, enumerate_out=None):
    """Enumerate every satisfying C matrix, then block it, re-solve. Writes one graph6
    line per solution. Solutions are LABELLED graphs: double lex leaves several
    labellings per isomorphism class. Returns the number of labelled solutions."""
    global TIME_MODEL_BUILDING, TIME_SAT, TIME_VERIFY, ABORT

    # build model
    t0 = time.perf_counter()
    clauses, nvars, ncard, cmap = encode_model(ell, kappa, n, enc=enc)
    TIME_MODEL_BUILDING += time.perf_counter() - t0
    cvars = [cmap[(v, i)] for v in range(n) for i in range(kappa)]

    print(f"  ell={ell} kappa={kappa} n={n}: ")

    # solve & block in a loop
    found = 0
    t0 = time.perf_counter()
    with Cadical300(bootstrap_with=clauses) as solver, open(enumerate_out, "a") as f:
        while not ABORT and solver.solve():
            pos = {l for l in solver.get_model() if l > 0}
            rows = [sorted(v for v in range(n) if cmap[(v, i)] in pos) for i in range(kappa)]
            t1 = time.perf_counter()
            ok, why = verify_solution(n, ell, kappa, rows)
            TIME_VERIFY += time.perf_counter() - t1
            if not ok:
                print(f"  VERIFICATION FAILED for {rows}: {why}")
                ABORT = True
                break
            f.write(to_graph6(rows, n) + "\n")
            found += 1
            # block this clique matrix, projected onto the C variables only,
            # so free auxiliary variables (isSuperset) cannot repeat it
            solver.add_clause([-x if x in pos else x for x in cvars])
    
    TIME_SAT += time.perf_counter() - t0
    print(f"{found} labelled solutions")
    return found


#############################################################################################
# main function: parse arguments, run multiple SAT instances
if __name__ == "__main__":
    t_total = time.perf_counter()

    parser = argparse.ArgumentParser(
        description="Finding ell-clique-minimal graphs with SAT "
                    "(PySAT encoding + CaDiCaL + LRAT certification)")
    parser.add_argument("-l", type=int, required=True,
                        help="ell: find an ell-clique-minimal graph")
    parser.add_argument("-k", type=int, required=False,
                        help="kappa: number of maximal cliques. If not given, run with "
                             +"ell <= kappa <= min(2(ell-1), ceil(ell+2*sqrt(ell-1)))")
    parser.add_argument("-n", type=int, required=False,
                        help="order of the graph. If not given, run with n = 1+2(ell-1)")
    
    parser.add_argument("-e", type=str, required=False, default="seqcounter",
                        help="cardinality encoding: seqcounter, totalizer, cardnetwrk, ...")
    
    parser.add_argument("--cadical", type=str, default="./cadical/build/cadical",
                        help="path to the standalone CaDiCaL binary")
    parser.add_argument("--checker", type=str, default="./cake_lpr/cake_lpr",
                        help="path to the LRAT checker (cake_lpr)")
    parser.add_argument("--proofs", type=str, default="./sat-proofs",
                        help="directory for the DIMACS and LRAT files")
    parser.add_argument("--delete-proof", action="store_true", dest="delete_proof",
                        help="delete the LRAT proof once it has been verified "
                             +"(since proofs can reach several GB). The DIMACS file is kept")
    parser.add_argument("--disable-proof", action="store_true", dest="disable_proof",
                        help="do not verify the proof by storing LRAT (for example because of insufficient "
                            +"disk space, as LRAT proofs can be >50 GB for \\ell=9)")
    parser.add_argument("--text-lrat", action="store_true", dest="text_lrat",
                        help="write the LRAT proof in text instead of binary format. "
                             +"Needed for lrat-check, which reads a binary proof "
                             +"without complaining and then never reports VERIFIED")
    parser.add_argument("--checker-arg", action="append", default=[], dest="checker_args",
                        help="extra argument for the checker, e.g. "
                            "--checker-arg=--CML_HEAP_SIZE=16384")
    parser.add_argument("--skip-runs", nargs=2, type=int, action="append", default=[], metavar=("KAPPA", "N"),
                        dest="skip_runs", help="which runs to skip (repeat the option for multiple skips)")
    parser.add_argument("--count-runs-only", action="store_true", default=False, dest="count_runs_only",
                        help="if this option is given, only count the number of SAT " \
                        "runs needed (kappa x n values)")

    parser.add_argument("--enumerate", type=str, default=None, metavar="FILE",
                        help="enumerate all ell-clique-minimal graphs with PySAT and save "
                                "them as graph6 to FILE. Deduplicate with "
                                "`labelg -q FILE | sort -u`. Without -k/-n: every kappa*n in our conjectured"
                                "linear window as kappa in [ell, 2(ell-1)] and every n in [1, 2(ell-1)]")
    
    args = parser.parse_args()
    ell = args.l
    enc = getattr(EncType, args.e)
    skip_runs = []
    for pair in args.skip_runs:
        skip_runs.append(tuple(pair))
    if len(skip_runs)>0:
        print(f"Will skip the following (kappa,ell) runs: {skip_runs}")

    print(f"Using PySAT version={pysat.__version__}")

    # enumerate using our encoding to verify the graphs against nauty-geng enumeration
    if args.enumerate is not None:
        ks = [args.k] if args.k is not None else range(ell, 2 * (ell - 1) + 1)  # +1 since range end is exclusive
        ns = [args.n] if args.n is not None else range(1, 2 * (ell - 1) + 1)
        total = 0

        # truncate file
        with open(args.enumerate, "w") as f:
            f.write("")

        for kappa in ks:
            for n in ns:
                if ABORT:
                    break
                total += enumerate_instance(ell, kappa, n, enc=enc, enumerate_out=args.enumerate)

        print(f"\n{total} labelled graphs written to {args.enumerate} "
              f"(SAT {TIME_SAT:.3f}s, verification {TIME_VERIFY:.3f}s).")
        if ABORT:
            print(f"ABORTED! Enumerated graphs are not complete.")
            exit(1)
        exit()

    # normal proof run (no enumeration)

    # check binaries exist
    for name, path in (("CaDiCaL", args.cadical), ("LRAT checker", args.checker)):
        if not os.path.exists(path):
            print(f"error: {name} binary not found at {path}", file=sys.stderr)
            sys.exit(1)
    print(f"Using CaDiCaL at {args.cadical} and checker at {args.checker}")

    common = dict(enc=enc, cadical=args.cadical, checker=args.checker,
                  proof_location=args.proofs, delete_proof=args.delete_proof,
                  text_lrat=args.text_lrat, disable_proof=args.disable_proof,
                  checker_args=args.checker_args)

    # both kappa and n given: run for only (ell,kappa,n)
    if args.k is not None and args.n is not None:
        solve_instance(ell, args.k, args.n, **common)
        exit()

    # kappa given, n not given: run for only (ell, kappa, 2(ell-1)+1)
    if args.k is not None:
        solve_instance(ell, args.k, **common)
        exit()

    kappa_upper_bound = min(2 * (ell - 1), math.ceil(ell + 2 * math.sqrt(ell - 1)))

    # n given, kappa not given: run for possible kappa values
    if args.n is not None:
        for kappa in range(ell, kappa_upper_bound + 1):
            if ABORT:
                break
            solve_instance(ell, kappa, args.n, **common)
            print()
        sys.exit()

    # given nothing: run all open values
    n_lower_bound = 2 * (ell - 1)  # verify that we find a solution here
    linear_bound_safe = True
    instances_count = 0
    for kappa in range(ell, kappa_upper_bound + 1):
        if ABORT:
            break

        n_bound_k_three_halves = math.floor((kappa + math.sqrt(2) * math.pow(kappa, 1.5)) / (1 + kappa - ell))
        n_bound_balogh_bollobas = (math.ceil(kappa / 2) * math.floor(kappa / 2) - 1) if kappa >= 8 else 2 * (kappa - 1)
        n_bound_recurrence = 3 * ell - 6  # assuming linear proofs for ell' < ell

        n_upper_bound = min(n_bound_k_three_halves, n_bound_balogh_bollobas, n_bound_recurrence)

        for n in range(n_lower_bound, n_upper_bound + 1):
            if ABORT:
                break

            # skip n = 2(ell-1) run when kappa > ell
            if n == n_lower_bound and kappa > ell:
                continue

            if (kappa,n) in skip_runs:
                print(f"SKIPPING kappa={kappa} n={n} run.")
                continue

            if args.count_runs_only:
                if n > n_lower_bound:
                    instances_count += 1
                continue

            found = solve_instance(ell, kappa, n, **common)
            if found and n > n_lower_bound:
                linear_bound_safe = False
                break
            print()

    if args.count_runs_only:
        print(f"SAT instances for ell={ell}: {instances_count} (only counting instances with n > 2(ell-1))")
        exit()
    
    print(f"\nTotal time: {time.perf_counter()-t_total:.3f}s "
          f"(model building {TIME_MODEL_BUILDING:.3f}s, "
          f"CaDiCaL {TIME_SAT:.3f}s, verification {TIME_VERIFY:.3f}s)")
    if ABORT:
        print("Aborted - the results above are NOT a complete proof.")
    elif linear_bound_safe:
        if len(skip_runs)>0:
            print(f"Proven by SAT: for ell={ell} no ell-clique-minimal graph of order "
                f"> 2(ell-1) = {2*(ell-1)} exists except for possibly the parameters [(kappa,n)]={skip_runs}"
                f"since they were skipped. Bound only proven for non-skipped runs.")
        else:
            print(f"Proven by SAT: for ell={ell} no ell-clique-minimal graph of order "
                f"> 2(ell-1) = {2*(ell-1)} exists.")

    else:
        print("Found a counterexample to the linear bound!")
