# Security policy

## Supported versions

Only the default branch (`main`) is supported.

## Reporting a vulnerability

Report it privately through GitHub: open the repository's Security tab and choose "Report a vulnerability" (private vulnerability reporting). Do not open a public issue for a vulnerability.

The application is local and offline: it binds `127.0.0.1` only and makes no external request. Reports about the Host and Origin checks, the Content-Security-Policy, request parsing, or any path that passes user text to code are in scope.
