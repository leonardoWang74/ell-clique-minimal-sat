/* 
run using the commands given in the Makefile (target "nauty-plugin").
 */

#include "plugin_core.h"
#include <stdio.h>
#include <string.h>

#ifndef ELL
#define ELL 7
#endif

/* Proven cutoffs for ell-clique-minimal graphs:
 *   |C_G| <= 2(ELL-1),  and every maximal clique has size <= 2(ELL-1)-1.
 * The omega cap also applies to every frontier graph (omega is monotone under
 * induced subgraphs) and is what makes the frontier finite: without it K_n has
 * one maximal clique and stays in the frontier forever. */
#define CLIQUE_CAP (2 * (ELL - 1) + 1)
#define OMEGA_CAP  (2 * (ELL - 1) - 1)

static long long cm_found = 0, cm_terminal = 0, cm_frontier = 0;
static int cm_largest = 0;

static long long cm_lvl_frontier[65];
static long long cm_visits = 0;

static void plugin_dump(void)
{
    int i;
    fprintf(stderr, "---ell=%d visits=%lld found=%lld\n", ELL, cm_visits, cm_found);
    for (i = 1; i <= 64; ++i)
        if (cm_lvl_frontier[i]>0) fprintf(stderr, "    frontier[%d] = %lld\n", i, cm_lvl_frontier[i]);
    fflush(stderr);
}

// global variables as parameters for bron-kerbosch
static int bk_ncliques; // number of maximal cliques found
static int bk_overflow; // 1 <=> found more than CLIQUE_CAP maximal cliques
static uint64_t bk_cliques[CLIQUE_CAP];  // list of maximal cliques (every clique is an integer as a bitset)

/** Bron-Kerbosch with pivot, with sets represented as uint64_t, stops when finding CLIQUE_CAP maximal cliques
 * [Eppstein et al. 2010 - Listing All Maximal Cliques in Sparse Graphs in Near-optimal Time, Figure 2: BronKerboschPivot]
 */
static void bron_kerbosch_up_to_2ell(const uint64_t *adj, uint64_t P, uint64_t R, uint64_t X)
{
    if (bk_overflow) return;

    // if $P \cup X = \emptyset$ -> report R as a maximal clique
    if (P == 0 && X == 0) {
        if (bk_ncliques >= CLIQUE_CAP) { bk_overflow = 1; return; }
        bk_cliques[bk_ncliques++] = R;
        return;
    }

    // choose a pivot $u \in P \cup X$. Tomita, Tanaka, Takahashi 2006: choose $u$ to maximize $|P \cap N(u)|$ with $N(u)$ being the neighborhood of $u$
    // [Tomita, Tanaka, Takahashi 2006 - The worst-case time complexity for generating all maximal cliques and computational experiments]
    uint64_t t = P | X; // union of sets
    int pivot = -1, best = -1;
    while (t) {
        // __builtin_ctzll: returns the number of trailing 0 bits starting a the least significant bit (LSB)
        int v = __builtin_ctzll(t);
        t &= t - 1; // set LSB = 0 -> loop

        // __builtin_popcountll: returns the number of 1 bits
        int c = __builtin_popcountll(P & adj[v]);
        if (c > best) {
            best = c;
            pivot = v;
        }
    }

    // for each vertex $v \in P \setminus N(u)$ do
    uint64_t cand = P & ~adj[pivot];
    while (cand) {
        int v = __builtin_ctzll(cand);
        cand &= cand - 1; // set LSB = 0 -> loop

        // BronKerboschPivot(P \cap N(v), R \cup \{v\}, X \cap N(v))
        bron_kerbosch_up_to_2ell(adj, P & adj[v], R | (1ULL << v), X & adj[v]);
        if (bk_overflow) return;

        // P \leftarrow P \setminus \{v\}
        // X \leftarrow X \cup \{v\}
        P &= ~(1ULL << v);
        X |=  (1ULL << v);
    }
}

/* checking the condition for ell-clique-minimality */
static int is_ell_clique_minimal(int n, int m)
{
    // m \leq 2(\ell-1) already since we only test graphs after adding 
    // one vertex to a graph with $\leq \ell-1$ maximal cliques
    int cnt[64];
    const int need = 1 + m - ELL;
    int a, b, v;

    memset(cnt, 0, sizeof(int) * (size_t) n);

    for (a = 0; a < m; ++a) {
        uint64_t touched = 0;
        for (b = 0; b < m; ++b) {
            if (b == a) continue;
            uint64_t d = bk_cliques[a] & ~bk_cliques[b];
            if (d != 0 && (d & (d - 1)) == 0 && (touched & d) == 0) {
                touched |= d;
                cnt[__builtin_ctzll(d)]++;
            }
        }
    }

    for (v = 0; v < n; ++v)
        if (cnt[v] < need) return 0;
    return 1;
}

// given a graph by nauty-geng. Returns 1 if the graph should be pruned (not further expanded)
int given_graph(int n, const uint64_t *adj)
{
    // if (++cm_visits % 5000000 == 0) plugin_dump();
    if (n > 64) return 1;

    // calculate maximal cliques of the graph
    bk_ncliques = 0;
    bk_overflow = 0;
    bron_kerbosch_up_to_2ell(adj, (n == 64) ? ~0ULL : ((1ULL << n) - 1), 0ULL, 0ULL);

    // > 2(ELL-1) cliques (cannot be ell-clique-minimal)
    if (bk_overflow) {
        ++cm_terminal;
        return 1;
    }

    int kappa = bk_ncliques;

    if (kappa < ELL) { // frontier
        for (int i = 0; i < kappa; ++i)
            if (__builtin_popcountll(bk_cliques[i]) > OMEGA_CAP) return 1;
        ++cm_frontier;
        ++cm_lvl_frontier[n];
        return 0;
    }

    ++cm_terminal;

    if (is_ell_clique_minimal(n, kappa)) {
        ++cm_found;
        if (n > cm_largest) cm_largest = n;
        printf("MINIMAL ell=%d n=%d k=%d\n", ELL, n, kappa);
        for (int i = 0; i < n; ++i) {
            printf("   adj[%d] =", i);
            for (int j = 0; j < n; ++j)
                if (adj[i] & (1ULL << j)) printf(" %d", j);
            putchar('\n');
        }
        fflush(stdout);
    }
    return 1;
}

void plugin_report(double cpu)
{
    plugin_dump();
    printf("\n# ell=%d : %lld minimal graphs, largest n=%d, "
           "conjecture 2(ell-1)=%d %s\n",
           ELL, cm_found, cm_largest, 2 * (ELL - 1),
           (cm_largest <= 2 * (ELL - 1)) ? "OK" : "*** VIOLATED ***");
    printf("# frontier=%lld terminal=%lld cpu=%.2fs\n",
           cm_frontier, cm_terminal, cpu);
}
