ACTIVATE=. venv/bin/activate
PYTHON3=python3
# PYTHON3=python3.9
VERSION=1.0.0

venv:
	${PYTHON3} -m venv venv

build/install: venv requirements.txt
	${ACTIVATE} && pip install --upgrade pip wheel
	${ACTIVATE} && pip install -r requirements.txt
	mkdir -p build && touch build/install

install: build/install

freeze:
	${ACTIVATE} && pip freeze | sed '/pkg-resources==0.0.0/d' > requirements.txt

clean-install:
	rm -rf venv install

clean:
	rm -rf */__pycache__ dist

autoformat: install
	${ACTIVATE} && yapf --in-place *.py --style .yapfrc

check-format: install
	${ACTIVATE} && yapf --diff *.py --style .yapfrc

lint: install
	${ACTIVATE} && pylint *.py
