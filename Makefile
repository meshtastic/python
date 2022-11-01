# only run the fast unit tests
test:
	pytest -m unit

# only run the smoke tests against the virtual device
virt:
	pytest -m smokevirt

# run the smoke1 test (after doing a factory reset and unplugging/replugging in device)
smoke1:
	pytest -m smoke1 -s -vv

# local install
install:
	pip install .

# generate the docs (for local use)
docs:
	pdoc3 --html -f --output-dir docs meshtastic

# lint the codebase
lint:
	pylint meshtastic examples

# show the slowest unit tests
slow:
	pytest -m unit --durations=5

protobufs: FORCE
	git submodule update --init --recursive
	git pull --rebase
	git submodule update --remote --merge
	./bin/regen-protobufs.sh

# run the coverage report and open results in a browser
cov:
	pytest --cov-report html --cov=meshtastic
	# on mac, this will open the coverage report in a browser
	open htmlcov/index.html

# run cli examples
examples: FORCE
	pytest -mexamples

# Makefile hack to get the examples to always run
FORCE: ;
