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

unsigned long foundEllMinimalGraphs = 0;
void testEllCliqueMinimal(int graphsCount, std::string line, int ell) {
    Graph GraphValue = Graph::parse_graph6(line);
    Graph* G = &GraphValue;
    ++iterationCount;

    // get all cliques
    auto cliqueInfo = G->getMaximalCliques();

    if((int)cliqueInfo.cliqueList.size() >= 2*(ell-1)) {
        ++foundEllMinimalGraphs;
        std::cerr << "Graph "<<graphsCount<<": "<<line<<" has kappa ="<<cliqueInfo.cliqueList.size()<<" >= 2(ell-1). Found "<<foundEllMinimalGraphs<<" "<<ell<<"-clique-minimal graphs\n";
        std::cout << line<<"\n";
    }
}

int main(int argc, char* argv[]) {
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

            // std::cerr << "worker id="<<w<<" finished.\n";

            fclose(stream);
            exit(0);
        }

        close(pipes[w][0]); // parent closes read end
    }

    // parent distributes graphs
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

    return 0;
}
