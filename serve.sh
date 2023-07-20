#!/bin/bash
gunicorn --worker-class eventlet -w 1 --thread 50 -b :1234  --capture-output --log-level debug server:app