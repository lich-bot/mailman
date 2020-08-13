================================================
Mailman - The GNU Mailing List Management System
================================================

.. image:: https://gitlab.com/mailman/mailman/badges/master/build.svg
    :target: https://gitlab.com/mailman/mailman/commits/master

.. image:: https://readthedocs.org/projects/mailman/badge
    :target: https://mailman.readthedocs.io

.. image:: https://img.shields.io/pypi/v/mailman.svg
    :target: https://pypi.org/project/mailman/

.. image:: https://img.shields.io/pypi/dm/mailman.svg
    :target: https://pypi.org/project/mailman/

Copyright (C) 1998-2019 by the Free Software Foundation, Inc.

This is GNU Mailman, a mailing list management system distributed under the
terms of the GNU General Public License (GPL) version 3 or later.  The name of
this software is spelled "Mailman" with a leading capital 'M' but with a lower
case second 'm'.  Any other spelling is incorrect.

Technically speaking, you are reading the documentation for Mailman Core.  The
full `Mailman 3 suite <http://docs.mailman3.org>`_ includes a web user
interface called Postorius, a web archiver called HyperKitty, and a few other
components.  If you're looking for instructions on installing the full suite,
read that documentation.

Mailman is written in Python which is available for all platforms that Python
is supported on, including GNU/Linux and most other Unix-like operating
systems (e.g. Solaris, \*BSD, MacOSX, etc.).  Mailman is not supported on
Windows, although web and mail clients on any platform should be able to
interact with Mailman just fine.

The Mailman home page is:

    http://www.list.org

and there is a community driven wiki at

    http://wiki.list.org

For more information on Mailman, see the above web sites, or the
:ref:`documentation provided with this software <start-here>`.


Table of Contents
=================

.. toctree::
    :glob:
    :maxdepth: 1

    src/mailman/docs/introduction
    src/mailman/docs/release-notes
    src/mailman/docs/install
    src/mailman/config/docs/config
    src/mailman/docs/database
    src/mailman/docs/mta
    src/mailman/docs/postorius
    src/mailman/docs/hyperkitty
    src/mailman/docs/documentation
    src/mailman/plugins/docs/intro
    src/mailman/docs/contribute
    src/mailman/docs/STYLEGUIDE
    src/mailman/docs/internationalization
    src/mailman/docs/architecture
    src/mailman/docs/8-miles-high
    src/mailman/docs/NEWS
    src/mailman/docs/ACKNOWLEDGMENTS


REST API
--------

.. toctree::
    :maxdepth: 2
    :caption: REST API

    src/mailman/rest/docs/rest


Mailman modules
---------------

These documents are generated from the internal module documentation.

.. toctree::
    :maxdepth: 1
    :caption: Mailman Modules

    src/mailman/model/docs/model
    src/mailman/runners/docs/runners
    src/mailman/chains/docs/chains
    src/mailman/rules/docs/rules
    src/mailman/handlers/docs/handlers
    src/mailman/core/docs/core
    src/mailman/app/docs/app
    src/mailman/styles/docs/styles
    src/mailman/archiving/docs/common
    src/mailman/mta/docs/mta
    src/mailman/bin/docs/master
    src/mailman/commands/docs/commands
    contrib/README


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`





