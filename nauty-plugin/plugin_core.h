#ifndef CM_CORE_H
#define CM_CORE_H

#include <stdint.h>

/* Returns 1 if the graph should be pruned, 0 to keep extending the graph.
adj[i] is the neighbourhood bitmask of vertex i; n <= 64. */
int given_graph(int n, const uint64_t *adj);

void plugin_report(double cpu);

#endif
