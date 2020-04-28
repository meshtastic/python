rm dist/*
set -e
pandoc --from=markdown --to=rst --output=README README.md
python3 setup.py sdist bdist_wheel
python3 -m twine upload dist/*