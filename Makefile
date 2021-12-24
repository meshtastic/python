# unit test
test:
	pytest

# local install
install:
	pip install .

# lint the codebase
lint:
	pylint meshtastic

# show the slowest unit tests
slow:
	pytest --durations=0

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
