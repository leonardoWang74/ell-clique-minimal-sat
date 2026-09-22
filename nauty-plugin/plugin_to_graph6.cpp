/* Reads graphs in the "MINIMAL ell=.. n=.. k=.." dump format from stdin and
builds g6 string for each one.

Expected input:

MINIMAL ell=5 n=6 k=5
    adj[0] = 4 5
    adj[1] = 5
    adj[2] =
    adj[3] =
    adj[4] = 0
    adj[5] = 0 1

*/

#include "../Graph.h"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

struct PluginHeader {
    int ell = -1;
    int n = -1;
    int kappa = -1;
};

// strips leading whitespace.
std::string_view lstrip(std::string_view s) {
    std::size_t i = 0;
    while (i < s.size() && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
    return s.substr(i);
}

bool starts_with(std::string_view s, std::string_view prefix) {
    return s.size() >= prefix.size() && s.compare(0, prefix.size(), prefix) == 0;
}

// parses a "MINIMAL ell=5 n=6 k=5" line. key order is not assumed.
PluginHeader parse_header(std::string_view line, std::size_t line_no) {
    PluginHeader h;
    std::istringstream in{std::string(line)};
    std::string tok;
    in >> tok;  // "MINIMAL"
    while (in >> tok) {
        const std::size_t eq = tok.find('=');
        if (eq == std::string::npos) continue;
        const std::string key = tok.substr(0, eq);
        const int value = std::atoi(tok.c_str() + eq + 1);
        if (key == "ell") h.ell = value;
        else if (key == "n") h.n = value;
        else if (key == "k") h.kappa = value;
    }
    if (h.n < 0) {
        std::cerr << "line " << line_no << ": header without n\n";
        std::exit(1);
    }
    return h;
}

// parses "adj[4] = 0 1", writing the source index into `from` and the targets
// into `to`. Returns false if the line is not an adjacency line.
bool parse_adjacency(std::string_view line, int& from, std::vector<int>& to) {
    const std::size_t open = line.find("adj[");
    if (open == std::string_view::npos) return false;
    const std::size_t close = line.find(']', open);
    if (close == std::string_view::npos) return false;
    const std::size_t eq = line.find('=', close);
    if (eq == std::string_view::npos) return false;

    const std::string index{line.substr(open + 4, close - (open + 4))};
    from = std::atoi(index.c_str());

    to.clear();
    std::istringstream in{std::string(line.substr(eq + 1))};
    int w;
    while (in >> w) to.push_back(w);
    return true;
}

// called once per parsed graph.
void process_graph(const Graph& g) {
    std::cout << g.to_graph6() << '\n';
}

int main() {
    std::unique_ptr<Graph> graph;
    PluginHeader header;
    std::size_t count = 0;

    std::string raw;
    std::vector<int> targets;
    for (std::size_t line_no = 1; std::getline(std::cin, raw); ++line_no) {
        const std::string_view line = lstrip(raw);
        if (line.empty()) continue;

        if (starts_with(line, "MINIMAL")) {
            if (graph) process_graph(*graph/*, header, count*/);
            header = parse_header(line, line_no);
            graph = std::make_unique<Graph>(header.n);
            ++count;
            continue;
        }
        else if(starts_with(line, "#")){
            break;
        }

        int from = -1;
        if (!parse_adjacency(line, from, targets)) continue;  // unknown line
        if (!graph) {
            std::cerr << "line " << line_no << ": adj before any header\n";
            return 1;
        }
        if (from < 0 || from >= header.n) {
            std::cerr << "line " << line_no << ": index " << from
                      << " out of range for n=" << header.n << '\n';
            return 1;
        }
        for (const int to : targets) {
            if (to < 0 || to >= header.n) {
                std::cerr << "line " << line_no << ": neighbour " << to
                          << " out of range for n=" << header.n << '\n';
                return 1;
            }
            if (from < to) graph->edge_add(from, to);  // add each edge once
        }
    }
    if (graph) process_graph(*graph);

    std::cerr << count << " graph(s) read\n";
    return 0;
}

