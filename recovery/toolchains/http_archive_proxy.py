#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Plain-HTTP proxy that lets Xenial apt reach the Ubuntu archive over HTTPS.

Ubuntu 16.04 apt cannot use HTTPS without apt-transport-https, and some build hosts
only permit outbound HTTPS through an authenticated proxy. This adapter accepts apt's
plain-HTTP proxy requests for the Ubuntu archive hosts and fetches the same paths over
HTTPS (honouring HTTPS_PROXY). apt still verifies every Release signature and package
hash, so the adapter changes only the transport:

    python3 recovery/toolchains/http_archive_proxy.py 3142 &
    docker build --network host --build-arg http_proxy=http://127.0.0.1:3142 ...
"""

import http.server
import shutil
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request

ALLOWED_HOSTS = {"archive.ubuntu.com", "security.ubuntu.com"}
FORWARDED_HEADERS = ("content-length", "content-type", "last-modified", "etag", "content-range", "accept-ranges")


class ArchiveHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self, head=False):
        url = urllib.parse.urlsplit(self.path)
        if url.scheme != "http" or url.hostname not in ALLOWED_HOSTS:
            self.send_error(403, "Only the Ubuntu archive is proxied")
            return
        request = urllib.request.Request(
            urllib.parse.urlunsplit(("https", url.netloc, url.path, url.query, "")), method="HEAD" if head else "GET"
        )
        for name in ("Range", "If-Modified-Since", "If-Range"):
            if self.headers.get(name):
                request.add_header(name, self.headers[name])
        try:
            response = urllib.request.urlopen(request, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        self.send_response(response.status if hasattr(response, "status") else response.code)
        for name, value in response.headers.items():
            if name.lower() in FORWARDED_HEADERS:
                self.send_header(name, value)
        if response.headers.get("Content-Length") is None and not head:
            body = response.read()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.end_headers()
        if not head:
            shutil.copyfileobj(response, self.wfile, 1 << 20)

    def do_HEAD(self):
        self.do_GET(head=True)


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    ThreadingServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 3142), ArchiveHandler).serve_forever()
