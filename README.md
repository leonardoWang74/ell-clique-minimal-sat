Requirements: installed `make, python3`, `g++`, `gcc, git, diff` commands, bash commansd like `cat`, `cd`, and `mkdir`, 8 GB free disk space, and 2 GB memory (RAM) for $\ell \leq 8$. To run the SAT solver on $\ell=9$ at least 70 GB free disk space (LRAT file size), and at least 16 GB of memory (verifying the LRAT) are required.

Notable Makefile targets:
- Run `make sat` to run the SAT formulation for $\ell=\{6,7,8\}$ to show UNSAT for the unproven $(kappa,n)$ window and the LRAT proofs will be located in the folder `./sat-proofs` (~40 minutes running time with an 3.1GHz Intel Core i7). After showing UNSAT for every instance, the linear bound $n \leq 2(\ell-1)$ follows for $\ell \leq 8$.
- Run `make sat9` to run the SAT formulation for $\ell = 9$ (~16 hours running time with an 3.1GHz Intel Core i7). After showing UNSAT for every instance, the linear bound $n \leq 2(\ell-1)$ follows for $\ell = 9$.
- Run `make sat-vs-nauty-verification` to run the SAT enumeration and nauty-plugin enumeration to verify the SAT formulation against the nauty-geng plugin (~6 hours running time with an 3.1GHz Intel Core i7 to enumerate graphs with the SAT formulation). The graph6 list of found graphs will be in the folder `./sat-enumerate`.
- Run `make nauty-plugin` to only run the nauty-geng plugin to enumerate $\ell$-clique minimal graphs for $\ell \leq 7$ (~2 minutes running time with an 3.1GHz Intel Core i7). The graph6 list of found graphs will be in the folder `./nauty-plugin/result`.
- Run `make testWithNauty` to verify the nauty-geng plugin (~1 hour running time with an 3.1GHz Intel Core i7).

Note the SAT formulation can also be run for any $(\ell, \kappa, n)$ triple, by running `.venv/bin/python3 sat.py -l ELL -k KAPPA -n N` with ELL, KAPPA, and N as integers. Run `.venv/bin/python3 sat.py --help` to see all options.
