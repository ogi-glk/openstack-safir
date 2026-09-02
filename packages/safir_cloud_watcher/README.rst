===================
Safir Cloud Watcher
===================

.. image:: images/safir_cloud_watcher_icon.png
    :alt: Safir Cloud Watcher
    :align: center


Licence Tracker as a Service component
++++++++++++++++++++++++++++++++++++++

Goal
----

Safir Cloud Watcher aims at tracking licence and limit states in a Safir Cloud environment.

Controller nodes' hardware ID or a serial key can be used as licence, which is stored at
Safir Cloud Watcher's database by Ansible installation scripts. Hypervisor or CPU counts
are used as limit values, which is also stored at database during installation.

This project needs to be obfuscated before installation to keep the code unchanged,
moreover it includes decryption keys.

Most parts of Safir Cloud Watcher are modular so you can easily extend the base code to
address your particular use case.


Trying it
---------

Safir Cloud Watcher can be deployed with devstack, more information can be found in the
devstack/README.rst file.


Deploying it in production
--------------------------

Safir Cloud Watcher can be deployed in production on OpenStack environments, for
more information check the INSTALL.rst file. Due to
oslo libraries new namespace backward compatibility is not possible. If you
want to install it on an older system, use a virtualenv.
