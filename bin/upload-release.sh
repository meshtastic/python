rm dist/*
set -e

poetry build
poetry run pytest
poetry publish 
#python3 setup.py sdist bdist_wheel
#python3 -m twine upload dist/*
