#!/bin/bash

mkdir -p /run/isolate
mkdir -p /sys/fs/cgroup/isolate
echo "/sys/fs/cgroup/isolate" > /run/isolate/cgroup
echo "+memory +cpu +pids" > /sys/fs/cgroup/isolate/cgroup.subtree_control
exec "$@"
