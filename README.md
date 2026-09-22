Requirements: `python3.10` command.

Run `make sat-vs-nauty-verification` to run the SAT enumeration and nauty-plugin enumeration to verify the SAT formulation against the nauty-geng plugin. The graph6 list of found graphs will be in the folder `./sat-enumerate`.

Run `make sat` to run the SAT formulation for ell=6,7,8 to show UNSAT for the unproven (kappa,n) window and the LRAT proofs will be located in the folder `./sat-proofs`.

Run `make testWithNauty` to verify the nauty-geng plugin.
