#!/usr/bin/bash
set -e

# run dfm poc start in prepare only mode which prepares the folder structure
dfm poc cleanup -f earth2
rm -f ./workspace/flare.pid
dfm poc start -f earth2 --prepare-only 

# change permissions to give others rwx access to transfer folder as else we get permission errors on the client side
chmod o+rwx ./workspace/earth2_poc/federation/prod_00/homesite@earth2.nvidia.com/transfer

# now we can start the federation
dfm poc start -f earth2 --skip-prepare

# display logs and keep container running until tail exits
tail -f ./workspace/flare.log ./workspace/earth2_poc/federation/prod_00/client1/log.txt
