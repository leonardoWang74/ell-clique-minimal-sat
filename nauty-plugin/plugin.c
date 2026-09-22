/* plugin.c
 * included into nauty's geng.c with -DPLUGIN.
 * converts nauty's graph into plain bitmasks and calls
 * plugin_core. */

#include "plugin_core.h"

int cliqueminimal_prune(graph *g, int n, int maxn)
{
    uint64_t adj[64];
    int i, j;

    if (n > 64) return 1;

    for (i = 0; i < n; ++i) {
        set *gi = GRAPHROW(g, i, 1);
        adj[i] = 0;
        for (j = 0; j < n; ++j)
            if (j != i && ISELEMENT(gi, j)) adj[i] |= 1ULL << j;
    }
    return given_graph(n, adj);
}

void cliqueminimal_summary(nauty_counter nout, double cpu)
{
    plugin_report(cpu);
}
