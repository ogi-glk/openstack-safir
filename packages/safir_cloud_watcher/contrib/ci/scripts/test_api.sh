#!/usr/bin/env bash

test_handshake ()
{
    echo "GET http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/handshake"
    curl -H "X-Auth-Token: $OSTOKEN" "http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/handshake/SafirCloudWatcher"
}

test_licence ()
{
    echo "GET http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence"
    curl -H "X-Auth-Token: $OSTOKEN" "http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence/"
    echo "PUT http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence"
    curl -X PUT -i -H "Content-Type: application/json" -H "Accept: application/json"  -H "X-Auth-Token: $OSTOKEN"  "http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence" -d '{"licence_key": "'$ENCRYPTED_LICENCE_KEY'", "notification_address": "'$CLOUD_ADMIN_EMAIL_ADDRESS'"}'
    echo "DELETE http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence"
    curl -X "DELETE" -i -H "Content-Type: application/json" -H "Accept: application/json"  -H "X-Auth-Token: $OSTOKEN"  "http://$SAFIR_CLOUD_WATCHER_ENDPOINT_IP:8839/v1/licence"
}

source /opt/stack/devstack/openrc admin admin
OSTOKEN=$(openstack token issue -c "id" -f value)
SAFIR_CLOUD_WATCHER_ENDPOINT_IP="192.168.5.29"
ENCRYPTED_LICENCE_KEY="gAAAAABm_T_JzXsdeZNXZoh8KiCImZGqyDJ0NBZBno2VYcig_zYPDHiJGRfI01LOKQSOs_8PPyJ2DxGfqAULA8JKSWkO6jycakeAWs7xaFyxB7UEySxuxEP5JJHUGy0JfJDKpgW3KHOkEm_nIkfS6b2ftKZmqaHK2Q=="
CLOUD_ADMIN_EMAIL_ADDRESS="ozkan.esra@tubitak.gov.tr"

# Policy should allow
test_handshake
test_licence


source /opt/stack/devstack/openrc demo demo
OSTOKEN=$(openstack token issue -c "id" -f value)

# Policy should not allow
test_handshake
test_licence