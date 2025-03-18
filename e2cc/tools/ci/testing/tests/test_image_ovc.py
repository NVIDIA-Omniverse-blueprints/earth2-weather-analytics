# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import argparse
import json
import logging as log
import os
import requests
from requests.adapters import HTTPAdapter, Retry
import socket
import sys
import time

PASS=True
FAIL=False

RETRIES=100
SSL=True
ALIVE_DELAY=30
ALIVE_WAIT_FOR_POD=120

log.basicConfig(level=log.INFO)

def main(args):
    try:
        test_image(args)
    except Exception as e:
        log.error("Exception: " + str(e))
        log.error("Test FAILED!")
        return FAIL
    log.info("Test PASSED!")
    return PASS

def test_image(args):
    url = normalize_url(args.url)
    if not url.endswith("/session"):
        url = url + "/session"
    log.info(f"Connecting to {url}")
    headers = {
        "authorization": f"Bearer {args.token}",
        "bearer-type": "nucleus",
        "content-type": "application/json"
    }
    body = {
        # We don't really use url, but OVC requires a well-formed url here
        "url": "omniverse://store.devtest.az.cloud.omniverse.nvidia.com",
        "access_token": args.token,
        "spec": {
            "image": args.image,
            "streaming_mode": "secure",
            "kit_env": {}
        }
    }
    log.info(f"Request headers: {headers}")
    log.info(f"Request body: {body}")
    # Enable two levels of retries - on HTTPS level to protect from network glitches etc.
    # and another level to enable waiting for not pre-warmed up image to start
    i = RETRIES
    session = requests.Session()
    retries = Retry(total=100,
                    backoff_factor=0.5,
                    status_forcelist=[ 500, 502, 503, 504 ])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    while i > 0:
        r = None
        timeout = False
        try:
            r = session.post(url, data=json.dumps(body), headers=headers, timeout=500, verify=SSL)
            log.info(f"Response code: {r.status_code}")
        except requests.Timeout:
            log.warning("POST request timed out, but not giving up yet")
            timeout = True
        # If we try a new, not pre-warmed up image, we will get 500 for some time - OVC must
        # catch up and cache the image
        if timeout or r.status_code in [500, 501, 503]:
            i -= 1
            log.warning(f"Session start failed, but, retrying in {ALIVE_DELAY}s...")
            time.sleep(ALIVE_DELAY)
            timeout =  False
        else:
            post_data = r.json()
            log.info("Response data:")
            log.info(post_data)
            break
    assert r.status_code == 200
    session_id = post_data["session_id"]
    con_str = post_data["redirect"].split("?")[1]
    for s in con_str.split("&"):
        if "=" in s:
            a, b = s.split("=")
            if a == "signalingserver":
                signaling_server = b
            elif a == "signalingport":
                signaling_port = int(b)
    assert signaling_server is not None
    assert signaling_port is not None
    log.info(f"Waiting {ALIVE_WAIT_FOR_POD}s to see if pod does not crash soon after starting")
    time.sleep(ALIVE_WAIT_FOR_POD)
    try:
        # We should have our session running
        r = session.get(url + "/" + session_id, headers=headers, timeout=5, verify=SSL)
        assert r.status_code == 200
        resp = r.json()
        log.info(f"Received response for get session: {json.dumps(resp, indent=4)}")
        assert resp["session"]["status"]["phase"] == "Running"
        # Just check if we can connect and send something
        check_streaming_connectivity(signaling_server, signaling_port)
    finally:
        # OK, now we need to tear down the session, even if test failed
        if not args.skip_delete:
            r = requests.delete(f"{url}/{session_id}", headers=headers, timeout=5, verify=SSL)
            assert r.status_code == 200
            log.info(f"Response to DELETE request: {r.text}")
        else:
            log.warning("Not deleting session, --skip-delete arg provided")
       # If we haven't thrown - great!
    log.info("Test completed.")

def normalize_url(url):
    if not url.startswith('https'):
        url = f'https://{url}'
    return url.rstrip('/')

def check_streaming_connectivity(signaling_server, signaling_port):
    max_connection_retries = 30
    retries = max_connection_retries

    # resolve hostname
    resolved_host = socket.getaddrinfo(signaling_server, signaling_port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    if len(resolved_host) == 0:
        error_msg = f"Could not resolve Host: ({signaling_server}, {signaling_port})"
        log.error(error_msg)
        raise RuntimeError(error_msg)
    log.info(f"Host resolved to: {resolved_host[0][4]}")

    while retries >= 0:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)

                log.info(f"Connecting to {signaling_server} on port {signaling_port}; retries left: {retries}")
                s.connect(resolved_host[0][4])
                log.info(f"Connected! Sending...")
                s.sendall(b"JUST A TEST")
                break
        except BaseException as e:
            log.info(f"Attempt failed with exception of type {type(e)}: '{str(e)}'")
            retries = retries - 1
    # If we don't get negative retries value - we succeeded... finally.
    assert retries >= 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--token",
        default=os.environ.get("NUCLEUS_TOKEN"),
        type=str,
        nargs="?",
        help="Nucleus auth token"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="E2CC image to use (must be in nvcr.io)"
    )
    parser.add_argument(
        "--url",
        default="https://streaming-session.ovx-prd31-sjc11.proxy.ace.ngc.nvidia.com/",
        type=str,
        help="URL to OVC instance to use (session service)"
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Do not stop the session before exiting"
    )

    args = parser.parse_args()
    if not args.token:
        log.error("No Nucleus token provided - either use --token parameter or set NUCLEUS_TOKEN")
        sys.exit(1)
    if not args.image:
        log.error("No image provided")
        sys.exit(1)

    # Main job
    sys.exit(not (main(args) == PASS))
