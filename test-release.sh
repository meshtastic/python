rm dist/*
set -e

pydoc3 -w meshtastic
mv *.html doc

python3 setup.py sdist bdist_wheel
python3 -m twine check dist/*
# test the upload
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
echo "view the upload at https://test.pypi.org/ it it looks good upload for real"