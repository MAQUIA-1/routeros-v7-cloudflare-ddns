# RouterOS execution checks

Requirements: Python 3 with `pexpect`, `qemu-system-x86_64`, and a fresh official RouterOS 7.25 CHR raw image.

```sh
python tests/chr_smoke.py /path/to/chr-7.25.img
```

QEMU runs with a temporary snapshot. The image is not modified. The test replaces only the WAN interface, domain configuration, and API endpoint in a temporary copy of the updater, then exercises the real functions inside RouterOS with `read,test` permissions.

A local HTTP server simulates DNS records. No Cloudflare credentials or account are used. This checks parsing and execution, initial synchronization, disabled-address exclusion, unchanged IP, partial and total failures, HTTP error logging, WAN reversion, TestMode, proxy payloads, and overlapping runs.

The overlap check waits for the RouterOS job to finish, with a 30-second limit. Log assertions inspect script logs rather than configuration audit logs.

TLS certificate validation and live Cloudflare integration are outside this test. Console output is saved to a temporary log file printed at startup.
