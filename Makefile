
NAME=githistorian
VERSION=$(shell cat VERSION)

STESTDIR=/tmp/gh-stest
STESTENV=$(STESTDIR)/bin/activate
BTESTDIR=/tmp/gh-stest
BTESTENV=$(BTESTDIR)/bin/activate

TARGZ=dist/$(NAME)-$(shell cat VERSION).tar.gz
WHEEL=dist/$(NAME)-$(shell cat VERSION)-py3-none-any.whl

all: test

fullcheck: check scheck bcheck

check:
	@python3 setup.py check

scheck: $(TARGZ)
	@python3 -m venv $(STESTDIR)
	@. $(STESTENV) && pip3 install $(TARGZ)
	@. $(STESTENV) && $(NAME) --version

bcheck: $(WHEEL)
	@python3 -m venv $(BTESTDIR)
	@. $(BTESTDIR) && pip3 install $(WHEEL)
	@. $(BTESTDIR) && $(NAME) --version

install:
	@pip3 install --verbose --user .

test:
	@#$(NAME) -m1 < tests/m1-test-00.txt
	@$(NAME) -m1 < tests/m1-test-01.txt

clean:
	@python3 setup.py clean

veryclean: clean
	@rm -rf dist/ build/ $(STESTDIR) $(BTESTDIR)
	@find . -name '*.egg-info' | xargs rm -rf
	@find . -name __pycache__ | xargs rm -rf

dist:
	@python3 setup.py sdist bdist_wheel

$(TARGZ):
	@python3 setup.py sdist

$(WHEEL):
	@python3 setup.py bdist_wheel

publish: veryclean dist
	@python3 -m twine upload dist/*.whl dist/*.tar.gz

.PHONY: all check install clean veryclean dist

