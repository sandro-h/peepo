ACTIVATE=. venv/bin/activate
PYTHON3=python3
# PYTHON3=python3.9
VERSION=1.0.0

venv:
	${PYTHON3} -m venv venv

build/install: venv requirements.txt
	${ACTIVATE} && pip install --upgrade pip wheel
	${ACTIVATE} && pip install -r requirements.txt
	${ACTIVATE} && pip install -r requirements-dev.txt
	mkdir -p build && touch build/install

.PHONY: install
install: build/install

.PHONY: freeze
freeze:
	${ACTIVATE} && pip freeze | sed '/pkg-resources==0.0.0/d' > requirements-dev.txt
	echo "Reminder: non-dev requirements must be copied to requirements.txt by hand!"

.PHONY: clean-install
clean-install:
	rm -rf venv install

.PHONY: clean
clean:
	rm -rf */__pycache__ dist

.PHONY: autoformat
autoformat: install
	${ACTIVATE} && yapf --in-place *.py --style .yapfrc

.PHONY: check-format
check-format: install
	${ACTIVATE} && yapf --diff *.py --style .yapfrc

.PHONY: lint
lint: install
	${ACTIVATE} && pylint *.py

.PHONY: test
test: install
	${ACTIVATE} && pytest tests