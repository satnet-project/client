#!/bin/bash

if [ $1 == '-i' ];
then
	script_path="$( cd "$( dirname "$0" )" && pwd )"
	project_path=$( readlink -e "$script_path/.." )
	venv_path="$project_path/.venv"

	# Enable serial access
	currentUser=$(whoami)
	sudo usermod -a -G dialout $currentUser 

	# Install required packages
	sudo apt --assume-yes install build-essential 
	sudo apt --assume-yes install virtualenv
	sudo apt --assume-yes install python-qt4
	sudo apt --assume-yes install libqt4-dev 
	sudo apt --assume-yes install unzip
	sudo apt --assume-yes install python-pip
	sudo apt --assume-yes install python-dev
	sudo apt --assume-yes install libffi-dev
	sudo apt --assume-yes install libssl-dev
 	sudo apt --asumme-yes install libcanberra-gtk-module

	# Create a virtualenv
	virtualenv $venv_path
	source "$venv_path/bin/activate"
	pip install -r "$project_path/requirements.txt"

	# Downloading packages for GUI
	# Needed to install SIP first
	cd $venv_path
	mkdir build && cd build
	pip install SIP --allow-unverified SIP --download="."
	unzip sip*
	cd sip*
	python configure.py
	make
	sudo make install
	cd ../ && rm -r -f sip*

	# PyQt4 installation.
	wget http://downloads.sourceforge.net/project/pyqt/PyQt4/PyQt-4.11.4/PyQt-x11-gpl-4.11.4.tar.gz
	tar xvzf PyQt-x11-gpl-4.11.4.tar.gz
	cd PyQt-x11-gpl-4.11.4
	python ./configure.py --confirm-license -q /usr/bin/qmake-qt4
	make
	# Bug. Needed ldconfig, copy it from /usr/sbin
	cp /sbin/ldconfig ../../bin/
	sudo ldconfig
	sudo make install
	cd ../ && rm -r -f PyQt*

	# man page creation
	source "$venv_path/bin/activate"
	cd "$project_path/docs"
	make man
	cp _build/man/satnetclient.1 ../
	deactivate

elif [ $1 == '-circleCI' ];
then
	script_path="$( cd "$( dirname "$0" )" && pwd )"
	project_path=$( readlink -e "$script_path/.." )

    mkdir key
    # 1: Generate a Private Key
    echo '>>> Generating a private key'
    openssl genrsa -des3 -passout pass:satnet -out key/test.key 1024
    # 2: Generate a CSR (Certificate Signing Request)
    echo '>>> Generating a CSR'
    openssl req -new -key key/test.key -passin pass:satnet -out key/test.csr -subj /CN=example.humsat.org/ 
    # 3: Remove Passphrase from Private Key
    echo '>>> Removing passphrase from private key'
    openssl rsa -in key/test.key -passin pass:satnet -out key/test.key
    # 4: Generating a Self-Signed Certificate
    echo '>>> Generating a public key (certificate)'
    openssl x509 -req -days 365 -in key/test.csr -signkey key/test.key -out key/test.crt

    echo '>>> Generating key bundles'
    # 5: Generate server bundle (Certificate + Private key)
    cat key/test.crt key/test.key > key/server.pem
    # 6: Generate clients bundle (Certificate)
    cp key/test.crt key/public.pem

    mv key ../tests
    echo '>>> Python modules installation'
	pip install -r "$project_path/requirements-tests.txt"

	echo '>>> SIP installation'
	mkdir build && cd build
	pip install SIP --allow-unverified SIP --download="."
	unzip sip*
	cd sip*
	python configure.py
	make
	make install
	sudo make install
	cd ../ && rm -r -f sip*

	echo '>>> PyQt4 installation'
	wget http://downloads.sourceforge.net/project/pyqt/PyQt4/PyQt-4.11.4/PyQt-x11-gpl-4.11.4.tar.gz
	tar xvzf PyQt-x11-gpl-4.11.4.tar.gz
	cd PyQt-x11-gpl-4.11.4
	python ./configure.py --confirm-license --no-designer-plugin -q /usr/bin/qmake-qt4
	make
	# Bug. Needed ldconfig, copy it from /usr/sbin
	cp /sbin/ldconfig ../../bin/

	sudo ldconfig
	sudo make install
	make install
	cd ../ && rm -r -f PyQt*

elif [ $1 == '-travisCI' ];
then
	script_path="$( cd "$( dirname "$0" )" && pwd )"
	project_path=$( readlink -e "$script_path/.." )

	echo "key"

    mkdir key

    pwd
    ls

    # 1: Generate a Private Key
    echo '>>> Generating a private key'
    openssl genrsa -des3 -passout pass:satnet -out key/test.key 1024
    # 2: Generate a CSR (Certificate Signing Request)
    echo '>>> Generating a CSR'
    openssl req -new -key key/test.key -passin pass:satnet -out key/test.csr -subj /CN=example.humsat.org/ 
    # 3: Remove Passphrase from Private Key
    echo '>>> Removing passphrase from private key'
    openssl rsa -in key/test.key -passin pass:satnet -out key/test.key
    # 4: Generating a Self-Signed Certificate
    echo '>>> Generating a public key (certificate)'
    openssl x509 -req -days 365 -in key/test.csr -signkey key/test.key -out key/test.crt

    echo '>>> Generating key bundles'
    # 5: Generate server bundle (Certificate + Private key)
    cat key/test.crt key/test.key > key/server.pem
    # 6: Generate clients bundle (Certificate)
    cp key/test.crt key/public.pem

    mv key ../tests

    pwd
    ls


    ls  ../tests

    echo '>>> Python modules installation'
    pip install coveralls
    pip install coverage
    pip install nose
	pip install -r "$project_path/requirements-tests.txt"

elif [ $1 == '-l' ];
then
	script_path="$( cd "$( dirname "$0" )" && pwd )"
	project_path=$( readlink -e "$script_path/.." )
	venv_path="$project_path/.venv_test"

	mkdir key
	# 1: Generate a Private Key
	echo '>>> Generating a private key'
	openssl genrsa -des3 -passout pass:satnet -out key/test.key 1024
	# 2: Generate a CSR (Certificate Signing Request)
	echo '>>> Generating a CSR'
	openssl req -new -key key/test.key -passin pass:satnet -out key/test.csr -subj /CN=example.humsat.org/ 
	# 3: Remove Passphrase from Private Key
	echo '>>> Removing passphrase from private key'
	openssl rsa -in key/test.key -passin pass:satnet -out key/test.key
	# 4: Generating a Self-Signed Certificate
	echo '>>> Generating a public key (certificate)'
	openssl x509 -req -days 365 -in key/test.csr -signkey key/test.key -out key/test.crt

	echo '>>> Generating key bundles'
	# 5: Generate server bundle (Certificate + Private key)
	cat key/test.crt key/test.key > key/server.pem
	# 6: Generate clients bundle (Certificate)
	cp key/test.crt key/public.pem

	v key ../tests

	# Create a virtualenv
	virtualenv $venv_path
	source "$venv_path/bin/activate"
	pip install -r "$project_path/requirements.txt"

	echo '>>> SIP installation'
	mkdir build && cd build
	pip install SIP --allow-unverified SIP --download="."
	unzip sip*
	cd sip*
	python configure.py
	make
	sudo make install
	cd ../ && rm -r -f sip*

	echo '>>> PyQt4 installation'
	wget http://downloads.sourceforge.net/project/pyqt/PyQt4/PyQt-4.11.4/PyQt-x11-gpl-4.11.4.tar.gz
	tar xvzf PyQt-x11-gpl-4.11.4.tar.gz
	cd PyQt-x11-gpl-4.11.4
	python ./configure.py --confirm-license --no-designer-plugin -q /usr/bin/qmake-qt4
	make
	# Bug. Needed ldconfig, copy it from /usr/sbin
	cp /sbin/ldconfig ../../bin/
	sudo ldconfig
	sudo make install
	cd ../ && rm -r -f PyQt*

fi




