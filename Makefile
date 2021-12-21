# unit test
test:
	pytest

# local install
install:
	pip install .

# lint the codebase
lint:
	pylint meshtastic

cov:
	pytest --cov-report html --cov=meshtastic
	# on mac, this will open the coverage report in a browser
	open htmlcov/index.html

# run cli examples
examples: FORCE
	pytest -mexamples

FORCE: ;
