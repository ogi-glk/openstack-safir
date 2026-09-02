===========================
Install Safir Cloud Watcher
===========================

Retrieve and install Safir Cloud Watcher
----------------------------------------

.. code-block:: bash

    $ git clone https://bitbucket.bilgem.tubitak.gov.tr/scm/sb/safir_cloud_watcher.git
    $ cd safir_cloud_watcher
    $ pip install .

This procedure installs the safir_cloud_watcher python library and the following executables:

safircloudwatcher-api: API service
safircloudwatcher-processor: Tracking and processing service
safircloudwatcher-dbsync: Tool to create and upgrade the database schema

Install sample configuration files
----------------------------------

.. code-block:: bash

    $ sudo mkdir /etc/safir_cloud_watcher
    $ tox -e genconfig
    $ sudo cp etc/safir_cloud_watcher/safir_cloud_watcher.conf.sample /etc/safir_cloud_watcher/safir_cloud_watcher.conf
    $ sudo cp etc/safir_cloud_watcher/policy.json /etc/safir_cloud_watcher
    $ sudo cp etc/safir_cloud_watcher/api_paste.ini /etc/safir_cloud_watcher

Create directories
------------------

.. code-block:: bash

    $ sudo mkdir /var/log/safir_cloud_watcher/
    $ sudo mkdir /var/lib/safir_cloud_watcher/
    $ sudo mkdir /var/www/safir_cloud_watcher/

Configure Safir Cloud Watcher
-----------------------------

Edit /etc/safir_cloud_watcher/safir_cloud_watcher.conf to configure the service.

Example configuration:

[DEFAULT]
verbose = True
debug = True
log_dir = /var/log/safir_cloud_watcher
transport_url = rabbit://RABBIT_USER:RABBIT_PASSWORD@RABBIT_HOST:5672/

[database]
connection = mysql://safir_cloud_watcher:SAFIR_CLOUD_WATCHER_DB_PASSWORD@DB_HOST/safir_cloud_watcher

[keystone_authtoken]
memcached_servers = localhost:11211
project_domain_name = Default
project_name = service
user_domain_name = Default
password = SAFIR_CLOUD_WATCHER_PASSWORD
username = safir_cloud_watcher
auth_url = http://KEYSTONE_HOST/identity
interface = public
auth_type = password

[openstack_auth]
memcached_servers = localhost:11211
project_domain_name = Default
project_name = service
user_domain_name = Default
password = SAFIR_CLOUD_WATCHER_PASSWORD
username = safir_cloud_watcher
auth_url = http://KEYSTONE_HOST/identity
interface = public
auth_type = password

[notifier]
smtp_host = smtp.domain.com
smtp_port = 587
sender_address = user@domain.com
sender_password = secret
use_tls = True

Setup the database and storage backend
--------------------------------------
MySQL/MariaDB is the recommended database engine. To setup the database, use the mysql client:

.. code-block:: bash

    $ mysql -uroot << EOF
    DROP DATABASE IF EXISTS safir_cloud_watcher;
    CREATE DATABASE safir_cloud_watcher;
    CREATE USER 'safir_cloud_watcher'@'localhost' IDENTIFIED BY 'SAFIR_CLOUD_WATCHER_DB_PASSWORD';
    GRANT ALL PRIVILEGES ON *.* TO 'safir_cloud_watcher'@'localhost';
    CREATE USER 'safir_cloud_watcher'@'%' IDENTIFIED BY 'SAFIR_CLOUD_WATCHER_DB_PASSWORD';
    GRANT ALL PRIVILEGES ON *.* TO 'safir_cloud_watcher'@'%';
    EOF

Run the database synchronisation scripts
----------------------------------------

.. code-block:: bash

    $ safircloudwatcher-dbsync upgrade

Set Licence
-----------

Generate licence key and insert to DB.

.. code-block:: python
    from cryptography.fernet import Fernet
    from cryptography.fernet import InvalidToken

    from datetime import datetime

    # Change the following values to generate a licence
    # and copy the licence string to safir_cloud_watcher.conf file
    destination_address = "TESTORTAMI"
    valid_until = datetime(2024, 1, 1)  # year, month, day
    hypervisor_limit = 5
    poc = 1  # 1 if true else 0

    # Do not modify the following code
    FERNET_KEY = b'9Ovua_Aud3bBzN3Vymd5VKNRBLr4yyM4TAcxSQ9v6n4='
    f = Fernet(FERNET_KEY)

    licence_txt = "TUBITAK_BILGEM_"

    licence_txt += destination_address.ljust(17)[:17]
    licence_txt += "_"

    licence_txt += valid_until.strftime("%Y%m%d")

    licence_txt += str(hypervisor_limit).zfill(5)

    licence_txt += str(poc)

    key_footer = "_SAFIR_BULUT"
    licence_txt += key_footer

    encrypted_licence_key = f.encrypt(licence_txt.encode())

    print("\n\n\n========= LICENSE BEGIN ======== ")
    print(encrypted_licence_key.decode())
    print("========== LICENSE END =========\n\n")

    encrypted_notification_counter = f.encrypt("0".encode())

    print("\n\n\n========= NOTIFICATION COUNTER BEGIN ======== ")
    print(encrypted_notification_counter.decode())
    print("========== NOTIFICATION COUNTER END =========\n\n")

.. code-block:: bash
    $ mysql -uroot << EOF
    USE safir_cloud_watcher;
    INSERT INTO licence (created_at, deleted, licence_key, notification_address, notification_counter) VALUES (NOW(), 0, <ENCRYPTED_LICENCE>, <CLOUD_ADMIN_EMAIL>, <ENCRYPTED_NOTIFICATION_COUNTER>);
    EOF

Setup Keystone
--------------

To integrate Safir Cloud Watcher to Keystone, run the following commands (as OpenStack administrator):

.. code-block:: bash

    $ openstack user create safir_cloud_watcher --password SAFIR_CLOUD_WATCHER_PASSWORD --email safir_cloud_watcher@localhost
    $ openstack role add --project service --user safir_cloud_watcher admin

Create the rating service and its endpoints:

.. code-block:: bash

    $ openstack service create cloud_watcher --name safir_cloud_watcher \
        --description "OpenStack Cloud Watcher Service"
    $ openstack endpoint create cloud_watcher --region RegionOne \
        public http://KEYSTONE_HOST:8839
    $ openstack endpoint create cloud_watcher --region RegionOne \
        admin http://KEYSTONE_HOST:8839
    $ openstack endpoint create cloud_watcher --region RegionOne \
        internal http://KEYSTONE_HOST:8839

Start the processing service
----------------------------

.. code-block:: bash

    $ safircloudwatcher-processor --config-file /etc/safir_cloud_watcher/safir_cloud_watcher.conf \
        --log-file /var/log/safir_cloud_watcher/safir_cloud_watcher.log

Installing the API behind mod_wsgi
----------------------------------

The file ``safir_cloud_watcher/api/app.wsgi`` sets up the V1 API WSGI
application. The file needs to be copied to ``/var/www/safir_cloud_watcher/``,
and should not need to be modified.

.. code-block:: bash

    $ cp safir_cloud_watcher/api/app.wsgi /var/www/safir_cloud_watcher/


The ``etc/apache2/safir_cloud_watcher.conf`` file contains example settings.

.. literalinclude:: ../../etc/apache2/safir_cloud_watcher.conf

1. On deb-based systems copy or symlink the file to
   ``/etc/apache2/sites-available``. For rpm-based systems the file will go in
   ``/etc/httpd/conf.d``.

2. Modify the ``WSGIDaemonProcess`` directive to set the ``user`` and
   ``group`` values to an appropriate user on your server. In many
   installations ``safircloudwatcher`` will be correct.

3. Enable the safir_cloud_watcher site. On deb-based systems::

      # a2ensite safir_cloud_watcher
      # service apache2 reload

   On rpm-based systems::

      # service httpd reload
