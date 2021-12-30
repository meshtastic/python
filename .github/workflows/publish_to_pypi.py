name: Publish PyPI

on: workflow_dispatch

jobs:
  build-n-publish:
    name: Build and publish distributions to PyPI
    runs-on: ubuntu-18.04
  steps:
    - uses: actions/checkout@master
    - name: Set up Python 3.9
      uses: actions/setup-python@v1
      with:
        python-version: 3.9
    - name: Install pypa/build
      run: >-
        python -m
        pip install
        build
        --user
    - name: Build a binary wheel and a source tarball
      run: >-
        python -m
        build
        --sdist
        --wheel
        --outdir dist/
        .
    - name: Publish to PyPI
      if: startsWith(github.ref, 'refs/tags')
      uses: pypa/gh-action-pypi-publish@master
      with:
        username: __token__
        password: ${{ secrets.PYPI_API_TOKEN }}
