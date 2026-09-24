# read the README.md for instructions on how to run
.PHONY: clean, satenumerate, sat, sat9, sms, nauty-plugin, nauty-plugin8

CXX = g++
CXXFLAGS = -O3 -std=c++17 -Wall -Wextra

all: sat-vs-nauty-verification sat
	echo "Ran our SAT enumeration, verified it with our nauty-geng plugin, and ran the UNSAT runs."

clean:
	rm -rf ./cadical ./cake_lpr ./sat-proofs ./sat-enumerate ./nauty-plugin/$(NAUTY_VERSION) \
		./nauty-plugin/$(NAUTY_VERSION).tar.gz ./nauty-plugin/*.o ./*.o plugin_to_graph6 testWithNauty

readme:
help:
	cat README.md

PY := .venv/bin/python3

.venv/.installed: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	touch .venv/.installed  # create the file so the target is satisfied

Graph.o: Graph.cpp Graph.h
	$(CXX) $(CXXFLAGS) -c Graph.cpp

# libraries: cadical, cake_lpr, nauty
NAUTY_VERSION = nauty2_9_3

cadical:  # download & compile the cadical binary
	git clone https://github.com/arminbiere/cadical.git
	cd cadical && ./configure && make

cake_lpr:  # download & compile the cake_lpr binary
	# download the proof checker cake_lpr
	git clone --depth 1 https://github.com/tanyongkiam/cake_lpr.git
	cd cake_lpr && make cake_lpr
	-sha256sum -c cake_lpr.sha256
	cd cake_lpr && git rev-parse HEAD  # was a36874a8b750b43fe4b385b8ddbf5b033e46a3fa
	cd cake_lpr && ./cake_lpr example.cnf example.lpr

LABELG = $(abspath ./nauty-plugin/$(NAUTY_VERSION)/labelg)
GENG = $(abspath ./nauty-plugin/$(NAUTY_VERSION)/geng)
nauty-plugin/$(NAUTY_VERSION):
	cd nauty-plugin; wget --no-check-certificate https://pallini.di.uniroma1.it/$(NAUTY_VERSION).tar.gz
	cd nauty-plugin; tar xvzf $(NAUTY_VERSION).tar.gz && cd $(NAUTY_VERSION) && ./configure && make

satenumerate: cadical cake_lpr .venv/.installed nauty-plugin/$(NAUTY_VERSION) # enumerate solutions (verify the SAT formulation)
	-mkdir sat-enumerate

	$(PY) sat.py -l 2 --enumerate ./sat-enumerate/enumerate-ell-2-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-2-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-2.g6
	rm ./sat-enumerate/enumerate-ell-2-duplicate.g6

	$(PY) sat.py -l 3 --enumerate ./sat-enumerate/enumerate-ell-3-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-3-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-3.g6
	rm ./sat-enumerate/enumerate-ell-3-duplicate.g6

	$(PY) sat.py -l 4 --enumerate ./sat-enumerate/enumerate-ell-4-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-4-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-4.g6
	rm ./sat-enumerate/enumerate-ell-4-duplicate.g6

	$(PY) sat.py -l 5 --enumerate ./sat-enumerate/enumerate-ell-5-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-5-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-5.g6
	rm ./sat-enumerate/enumerate-ell-5-duplicate.g6

	$(PY) sat.py -l 6 --enumerate ./sat-enumerate/enumerate-ell-6-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-6-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-6.g6
	rm ./sat-enumerate/enumerate-ell-6-duplicate.g6

	$(PY) sat.py -l 7 --enumerate ./sat-enumerate/enumerate-ell-7-duplicate.g6
	$(LABELG) -q ./sat-enumerate/enumerate-ell-7-duplicate.g6 | sort -u > ./sat-enumerate/enumerate-ell-7.g6
	rm ./sat-enumerate/enumerate-ell-7-duplicate.g6

# plugin_to_graph6 script: converts the output of the nauty plugin to graph6
nauty-plugin/plugin_to_graph6.o: Graph.h
	cd nauty-plugin; $(CXX) $(CXXFLAGS) -c plugin_to_graph6.cpp

nauty-plugin/plugin_to_graph6: nauty-plugin/plugin_to_graph6.o Graph.o
	cd nauty-plugin; $(CXX) $(CXXFLAGS) plugin_to_graph6.o ../Graph.o -o plugin_to_graph6

# nauty-geng plugin: enumerate ell-clique-minimal graphs (pruning while generating graphs)
NAUTYFLAGS = -DWORDSIZE=32 -DMAXN=WORDSIZE -O4 -mpopcnt -march=native \
		-DPRUNE=cliqueminimal_prune -DSUMMARY=cliqueminimal_summary \
		-DPLUGIN='"../plugin.c"' -o aa_geng_plugin geng.c ../plugin_core.o \
		gtoolsW.o nautyW1.o nautilW1.o naugraphW1.o schreierW.o naurng.o

nauty-plugin: nauty-plugin/$(NAUTY_VERSION) nauty-plugin/plugin_to_graph6
	-mkdir nauty-plugin/result

	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=2 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 2 -u > ./result/nauty-ell-2.txt
	cd nauty-plugin; cat ./result/nauty-ell-2.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-2.g6
	
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=3 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 4 -u > ./result/nauty-ell-3.txt
	cd nauty-plugin; cat ./result/nauty-ell-3.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-3.g6
	
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=4 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 6 -u > ./result/nauty-ell-4.txt
	cd nauty-plugin; cat ./result/nauty-ell-4.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-4.g6
	
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=5 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 8 -u > ./result/nauty-ell-5.txt
	cd nauty-plugin; cat ./result/nauty-ell-5.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-5.g6
	
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=6 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 10 -u > ./result/nauty-ell-6.txt
	cd nauty-plugin; cat ./result/nauty-ell-6.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-6.g6
	
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=7 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 12 -u > ./result/nauty-ell-7.txt
	cd nauty-plugin; cat ./result/nauty-ell-7.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-7.g6

nauty-plugin8:
	cd nauty-plugin; gcc -O3 -march=native -mpopcnt -DELL=8 -c plugin_core.c && cd $(NAUTY_VERSION) && gcc $(NAUTYFLAGS)
	cd nauty-plugin; ./$(NAUTY_VERSION)/aa_geng_plugin 14 -u > ./result/nauty-ell-8.txt
	cd nauty-plugin; cat ./result/nauty-ell-8.txt | ./plugin_to_graph6 | $(LABELG) -q | sort -u > ./result/nauty-ell-8.g6

# target verifying that nauty-plugin was run
nauty-plugin/result:
	make nauty-plugin

# verify the SAT enumeration finds the same graphs (up to isomorphism) = verification of the SAT encoding
sat-vs-nauty-verification: satenumerate nauty-plugin
	diff ./nauty-plugin/result/nauty-ell-2.g6 ./sat-enumerate/enumerate-ell-2.g6 && echo "    SAT enumeration identical to nauty plugin for ell=2"
	diff ./nauty-plugin/result/nauty-ell-3.g6 ./sat-enumerate/enumerate-ell-3.g6 && echo "    SAT enumeration identical to nauty plugin for ell=3"
	diff ./nauty-plugin/result/nauty-ell-4.g6 ./sat-enumerate/enumerate-ell-4.g6 && echo "    SAT enumeration identical to nauty plugin for ell=4"
	diff ./nauty-plugin/result/nauty-ell-5.g6 ./sat-enumerate/enumerate-ell-5.g6 && echo "    SAT enumeration identical to nauty plugin for ell=5"
	diff ./nauty-plugin/result/nauty-ell-6.g6 ./sat-enumerate/enumerate-ell-6.g6 && echo "    SAT enumeration identical to nauty plugin for ell=6"
	# diff ./nauty-plugin/result/nauty-ell-7.g6 ./sat-enumerate/enumerate-ell-7.g6 && echo "    SAT enumeration identical to nauty plugin for ell=7"

# SAT runs to prove UNSAT for n > 2(ell-1)
sat: cadical cake_lpr
	$(PY) sat.py -l 6
	$(PY) sat.py -l 7
	$(PY) sat.py -l 8

sat9: cadical cake_lpr
	# for ell=9 LRAT proofs are >50GB, so we delete LRAT files after verification
	$(PY) sat.py -l 9 --delete-proof --checker-arg=--CML_HEAP_SIZE=16384

# verify the nauty-geng plugin with a basic enumeration
testWithNauty.o: testWithNauty.cpp Graph.h
	$(CXX) $(CXXFLAGS) -c testWithNauty.cpp

testWithNauty-compile: testWithNauty.o Graph.o
	$(CXX) $(CXXFLAGS) testWithNauty.o Graph.o -o testWithNauty

testWithNauty: testWithNauty-compile nauty-plugin/result
	$(GENG) -q 2 | ./testWithNauty -l 2 -p 1 > ./sat-enumerate/nauty-basic-enumerate-ell2.txt
	cat ./sat-enumerate/nauty-basic-enumerate-ell2.txt | $(LABELG) -q | sort -u > ./sat-enumerate/nauty-basic-enumerate-ell2.g6

	$(GENG) -q 4 | ./testWithNauty -l 3 -p 1 > ./sat-enumerate/nauty-basic-enumerate-ell3.txt
	$(GENG) -q 3 | ./testWithNauty -l 3 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell3.txt
	$(GENG) -q 2 | ./testWithNauty -l 3 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell3.txt
	cat ./sat-enumerate/nauty-basic-enumerate-ell3.txt | $(LABELG) -q | sort -u > ./sat-enumerate/nauty-basic-enumerate-ell3.g6

	$(GENG) -q 6 | ./testWithNauty -l 4 -p 1 > ./sat-enumerate/nauty-basic-enumerate-ell4.txt
	$(GENG) -q 5 | ./testWithNauty -l 4 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell4.txt
	$(GENG) -q 4 | ./testWithNauty -l 4 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell4.txt
	$(GENG) -q 3 | ./testWithNauty -l 4 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell4.txt
	$(GENG) -q 2 | ./testWithNauty -l 4 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell4.txt
	cat ./sat-enumerate/nauty-basic-enumerate-ell4.txt | $(LABELG) -q | sort -u > ./sat-enumerate/nauty-basic-enumerate-ell4.g6

	$(GENG) -q 8 | ./testWithNauty -l 5 -p 1 > ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 7 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 6 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 5 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 4 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 3 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	$(GENG) -q 2 | ./testWithNauty -l 5 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell5.txt
	cat ./sat-enumerate/nauty-basic-enumerate-ell5.txt | $(LABELG) -q | sort -u > ./sat-enumerate/nauty-basic-enumerate-ell5.g6

	$(GENG) -q 10 | ./testWithNauty -l 6 -p 1 > ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 9 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 8 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 7 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 6 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 5 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 4 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 3 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	$(GENG) -q 2 | ./testWithNauty -l 6 -p 1 >> ./sat-enumerate/nauty-basic-enumerate-ell6.txt
	cat ./sat-enumerate/nauty-basic-enumerate-ell6.txt | $(LABELG) -q | sort -u > ./sat-enumerate/nauty-basic-enumerate-ell6.g6

	diff ./sat-enumerate/nauty-basic-enumerate-ell2.g6 ./nauty-plugin/result/nauty-ell-2.g6 && echo "Verified nauty-geng plugin for ell=2"
	diff ./sat-enumerate/nauty-basic-enumerate-ell3.g6 ./nauty-plugin/result/nauty-ell-3.g6 && echo "Verified nauty-geng plugin for ell=3"
	diff ./sat-enumerate/nauty-basic-enumerate-ell4.g6 ./nauty-plugin/result/nauty-ell-4.g6 && echo "Verified nauty-geng plugin for ell=4"
	diff ./sat-enumerate/nauty-basic-enumerate-ell5.g6 ./nauty-plugin/result/nauty-ell-5.g6 && echo "Verified nauty-geng plugin for ell=5"
	diff ./sat-enumerate/nauty-basic-enumerate-ell6.g6 ./nauty-plugin/result/nauty-ell-6.g6 && echo "Verified nauty-geng plugin for ell=6"

	echo "Verified nauty-geng plugin for ell=2,3,4,5,6"
