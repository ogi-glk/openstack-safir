#!/bin/bash 

BUILD_DIR=build/lib.linux-x86_64-cpython-312/
SAFIR_CLOUD_WACTHER_CYTHON_DIR=../safir_cloud_watcher_cython/

if [ ! -d "$BUILD_DIR" ]; then
  echo "$BUILD_DIR does not exist."
  exit 1
fi

if [ ! -d "$SAFIR_CLOUD_WACTHER_CYTHON_DIR" ]; then
  echo "$SAFIR_CLOUD_WACTHER_CYTHON_DIR does not exist."
  exit 1
fi

rm -rf $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/*

# Copy built .so files
cp -r $BUILD_DIR/safir_cloud_watcher/* $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/

# Copy release notes
cp -r ./releasenotes $SAFIR_CLOUD_WACTHER_CYTHON_DIR/releasenotes

# Create missing dirs
mkdir $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/db/sqlalchemy/migrations/
mkdir $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/event/data/

# Copy excluded .py files
cp ./safir_cloud_watcher/api/config.py $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/api/
cp ./safir_cloud_watcher/db/sqlalchemy/migrations/env.py $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/db/sqlalchemy/migrations/

# Copy other file types
cp ./safir_cloud_watcher/api/app.wsgi $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/api/
cp ./safir_cloud_watcher/db/sqlalchemy/alembic.ini $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/db/sqlalchemy/
cp ./safir_cloud_watcher/db/sqlalchemy/migrations/script.py.mako $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/db/sqlalchemy/migrations/
cp -r ./safir_cloud_watcher/db/sqlalchemy/migrations/versions $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/db/sqlalchemy/migrations/
cp -r ./safir_cloud_watcher/common/notification/templates $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/common/notification/
cp ./safir_cloud_watcher/event/data/* $SAFIR_CLOUD_WACTHER_CYTHON_DIR/safir_cloud_watcher/event/data/
