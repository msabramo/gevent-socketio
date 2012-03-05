pysocketio
==========

The `Socket.io`_ compatible server library for Python.

.. _Socket.io: http://socket.io/

Versioning
----------

We try to follow the `Socket.io` versions. This means that `pysocketio` version
developed to be compatible with `Socket.io` ``0.9.0`` will be versioned
``0.9.0.N``. It does not mean that version ``0.9.1.0`` will be incompatible with
a ``0.9.0`` client - that depends entirely on the `Socket.io`.

Installation
------------

Right now the code is only avaible on github, so you can either clone
this repository and install using ``setup.py``::

    git clone git://github.com/Smartupz/pysocketio.git
    cd pysocketio
    python setup.py install

or using ``pip``::

    pip install git+https://github.com/Smartupz/gevent-socketio.git


PS. We also have a ``setup.cfg``, so you can use distutils2/packaging if you want.

License
-------

This software is licensed under Simplified BSD License. For complete text see 
the ``LICENSE`` file.

Usage
-----

Coming soon! For now, checkout the ``examples`` directory (which may be a little
out of date, sorry!).

Authors
-------

Originaly created by Jeffrey Gelenes as `gevent-socketio`_. Currently maintaned
under new name by Łukasz Rekucki and Artur Wdowiarski from `Smartupz LLC`_.

.. _gevent-socketio: https://bitbucket.org/Jeffrey/gevent-socketio
.. _`Smartupz LLC`: http://www.smartupz.com/

