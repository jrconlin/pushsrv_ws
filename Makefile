APPNAME = pushsrv_ws
VE = virtualenv
PY = bin/python
PI = bin/pip
NO = bin/nosetests -s --with-xunit
NC = --with-coverage --cover-package=$(APPNAME)
PS = bin/pserve

all: build

build:
	$(VE) --no-site-packages .
	bin/easy_install -U distribute
	$(PI) install -r prod-reqs.txt
	cp -n pushsrv-dist.ini pushsrv.ini
	$(PY) setup.py develop

test:
	$(NO) $(APPNAME)

run:
	$(PY) pushsrv_ws/

#fl:
#   	FL_CONF_DIR=./fl $(PY) fl/test_simple.py

clean:
	rm -rf bin/ include/ lib/ local/ man/ src/
