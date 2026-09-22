/*
Test something on a nauty stream

Run using nauty geng
nauty-geng -c 14 | ./testWithNauty
*/
#include <unistd.h>
#include <sys/wait.h>

#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <algorithm>
#include <functional>
#include "Graph.h"

unsigned long iterationCount = 0;

// algorithm for checking if G is ell-clique-minimal in time O(3^{n/3} + n^2 * ell)
// note: we bound |\mathcal C_G| <= 2(\ell-1) and therefore need time O(n^2 * |\mathcal C_G|) = O(n^2 * ell)
bool isEllMinimal(Graph* G, MaximalCliquesInfo& cliqueInfo, int ell) {
    // does not contain at least ell maximal cliques
    if((int)cliqueInfo.cliqueList.size() < ell) return false;

    if(!cliqueInfo.cliqueList.empty() && cliqueInfo.cliqueSets.empty()) {
        for(const auto& clique : cliqueInfo.cliqueList) {
            cliqueInfo.cliqueSets.push_back(std::unordered_set<int>(clique.begin(), clique.end()));
        }
    }

    auto& C_F = cliqueInfo.cliqueSets;

    size_t cliqueCount = C_F.size();
    // contains too many maximal cliques. Cannot satisfy $|D(v)| \geq 1+|\mathcal C_G|-\ell$
    if((int)cliqueCount > 2*(ell-1)) return false;

    int dBound = 1 + (int)C_F.size() - ell;

    // D(v) for every vertex. D[v][i] = v is single distinguisher for clique i.
    // vertexDpairs[v][cliqueA] = true means that v has already incremented D(v) because of cliqueA
    std::vector<std::vector<bool>> vertexDpairs(G->n(), std::vector<bool>(cliqueCount, false));

    // |D(v)| for every vertex = count of cliques for which $v$ is the single distinguisher
    // = counting the entries of D(v) e.g. D(v) = {A,B,C} to |D(v)| = 3
    std::vector<int> vertexDcount(G->n(), 0);

    // pairwise differences -> D(v)
    // note that the clique sets contain at most the vertices V_F
    for(size_t i=0; i<cliqueCount; ++i) {
        for(size_t j=i+1; j<cliqueCount; ++j) {
            auto& cliqueA = C_F[i];
            auto& cliqueB = C_F[j];

            auto AwithoutB = Graph::set_difference(cliqueA, cliqueB);
            auto BwithoutA = Graph::set_difference(cliqueB, cliqueA);
            
            // single distinguisher exists
            if(AwithoutB.size() == 1) {
                int v = *AwithoutB.begin();

                // increment D(v) if D(v) does not yet contain A (count every vertex+clique pair only once)
                if(!vertexDpairs[v][i]){
                    vertexDpairs[v][i] = true;
                    ++vertexDcount[v];
                }
            }

            // single distinguisher exists
            if(BwithoutA.size() == 1) {
                int v = *BwithoutA.begin();

                // increment D(v) if D(v) does not yet contain B (count every vertex+clique pair only once)
                if(!vertexDpairs[v][j]){
                    vertexDpairs[v][j] = true;
                    ++vertexDcount[v];
                }
            }
        }
    }

    // look for vertex v \in V_F with |D(v)| < 1+|C_F|-ell
    for(int w = 0; w < G->n_signed(); ++w) {
        if(vertexDcount[w] >= dBound) continue;
        return false; // NOT ell-clique-minimal: this vertex violates the condition |D(v)| >= 1+|C_F|-ell
    }
    return true; // every vertex satisfies the condition |D(v)| >= 1+|C_F|-ell
}

unsigned long foundEllMinimalGraphs = 0;
void testEllCliqueMinimal(int graphsCount, std::string line, int ell) {
    Graph GraphValue = Graph::parse_graph6(line);
    Graph* G = &GraphValue;
    ++iterationCount;

    // get all cliques
    auto cliqueInfo = G->getMaximalCliques();

    if(isEllMinimal(G, cliqueInfo, ell)) {
        ++foundEllMinimalGraphs;
        std::cerr << "###### Graph "<<graphsCount<<": "<<line<<" is ell-clique-minimal. Found "<<foundEllMinimalGraphs<<" "<<ell<<"-clique-minimal graphs\n";
        std::cout << line<<"\n";
    }
    else {
        if(iterationCount % 100000 == 0) std::cerr << "Graph "<<graphsCount<<": "<<line<<" is not ell-clique-minimal. Found "<<foundEllMinimalGraphs<<" "<<ell<<"-clique-minimal graphs\n";
    }
}

int main(int argc, char* argv[]) {
    // print starting time
    {
        time_t timestamp = time(NULL);
        std::cerr << "\n\ntestWithNauty starting at: "<<ctime(&timestamp)<<"\n";
    }

    int workers = 2;
    int ell = -1;

    // parse options
    for(int i=1; i<argc; ++i) {
        std::string option = argv[i];

        if(option == "-l" && i+1 < argc) {
            ell = std::stoi(argv[++i]);
        }
        if(option == "-p" && i+1 < argc) {
            workers = std::stoi(argv[++i]);
        }
    }
    if(workers < 1) workers = 1;

    if(ell <= 1) {
        std::cout << "ell not given. Provide with `-l ELL` for example `-l 6` \n";
        exit(1);
    }

    // create pipes
    std::vector<int[2]> pipes(workers);
    for(int i=0;i<workers;i++) {
        if(pipe(pipes[i]) != 0) {
            std::cout << "Could not create pipe\n";
            exit(1);
        }
    }

    // fork workers
    for(int w=0; w<workers; ++w) {
        pid_t pid = fork();

        // child
        if(pid == 0) {
            // close unused pipes
            for(int j = 0; j < workers; ++j) {
                if(j == w) {
                    close(pipes[j][1]); // close write end of own pipe
                } else {
                    close(pipes[j][0]);
                    close(pipes[j][1]);
                }
            }

            FILE* stream = fdopen(pipes[w][0], "r");
            char buffer[4096];
            bool skipUntil = false;

            // run actual program
            int numberOfCliquesToSeparatorSize = 0;
            while(fgets(buffer, sizeof(buffer), stream)) {
                std::string msg(buffer);
                if(msg.empty()) continue;

                // split at first space
                size_t pos = msg.find(' ');
                if(pos == std::string::npos) continue;

                int graphsCount = std::stoi(msg.substr(0, pos));
                std::string line = msg.substr(pos + 1);

                // remove trailing newline
                if(!line.empty() && line.back() == '\n')
                    line.pop_back();

                if(skipUntil) {
                    if(graphsCount >= 13350000) skipUntil = false;
                    else continue;
                }

                testEllCliqueMinimal(graphsCount, line, ell);
            }

            std::cerr << "worker id="<<w<<" finished: needed separators found="<< numberOfCliquesToSeparatorSize<<"\n";

            fclose(stream);
            exit(0);
        }

        close(pipes[w][0]); // parent closes read end
    }

    // parent distributes graphs
    auto timeStart = TimeNow();
    std::string line;
    long graphsCount = 0;
    int currentWorker = 0;

    while (std::getline(std::cin, line)) {
        if(line.empty()) continue;

        ++graphsCount;
        std::string toSend = std::to_string(graphsCount) + " " + line + "\n";

        if( write(
            pipes[currentWorker][1],
            toSend.c_str(),
            toSend.size()
        ) < 0) {
            std::cerr << "Failed to write to worker "<<currentWorker<<"\n";
        }

        currentWorker = (currentWorker + 1) % workers;
    }

    // close pipes
    for(int i=0;i<workers;i++){
        close(pipes[i][1]);
    }

    // wait for workers
    for(int i=0;i<workers;i++){
        wait(nullptr);
    }

    long timeSpend = TimeDifference(timeStart);

    // print final output message
    std::cerr << "\ntestWithNauty finished."
        <<"\n\tReal time: "<<(timeSpend / 1000000.0)<<"s"
        <<"\n\n";

    return 0;
}
