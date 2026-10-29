# Cloudflare DDNS for MikroTik RouterOS v7

Monitors a specific network interface and automatically updates Cloudflare DNS A records when the interface IP address changes.

## Requirements

**Cloudflare API Token:**

- Zone - DNS - Edit
- Access to the configured zones and existing A records

**MikroTik Execution Permissions:**

- `read`, `write`, `policy`, `test`
- The scheduler policy must include all permissions declared by the script.

**Device-mode Policies:**

- `fetch` and `scheduler` must be allowed for scheduled execution
- See [MikroTik Device-mode documentation](https://manual.mikrotik.com/docs/system-information-and-utilities/device-mode/) for configuration

## Configuration

Edit `cloudflare-ddns.rsc` with your settings:

### WAN Interface
```routeros
:local WanInterface "ether1"
```
Set your actual WAN interface name.

### Domain and Credentials
```routeros
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
```

Replace with your actual values:
- `example.domain.com` - Domain name
- `your_cloudflare_zone_id` - Cloudflare Zone ID
- `your_cloudflare_api_token` - Cloudflare API Token

Multiple domains example:
```routeros
:local DomainConfigs {
    "domain1.com"={
        "DnsZoneID"="zone_id_1";
        "AuthToken"="api_token_1";
    };
    "domain2.com"={
        "DnsZoneID"="zone_id_2";
        "AuthToken"="api_token_2";
    };
}
```

### Optional Settings
```routeros
:local CloudflareProxy false
:local CheckCertificate false
:local TestMode false
```

- **CloudflareProxy**: Cloudflare proxy (orange cloud) for DNS records
- **CheckCertificate**: TLS certificate validation for API connections (requires valid CA certificates)
- **TestMode**: IP checks only; DNS records and the cached IP remain unchanged

## Installation

### 1. Set Script Permissions

Save the script as `cloudflare-ddns` in `/system script` before configuring permissions.

```routeros
/system script set cloudflare-ddns policy=read,write,policy,test
```

### 2. Create Scheduler
```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns policy=read,write,policy,test
```

The first scheduled execution occurs after one interval (5 minutes in this configuration).

## Tested Environment

MikroTik RB5009UG+S+, RouterOS 7.25.

## Changes — 2026-10-29

- Fixed skipped retries after DNS update failures when the WAN IP remains unchanged or returns to a previous address.
- Fixed TestMode modifying the cached IP and suppressing subsequent DNS updates.
- Added protection against concurrent script execution.
- Excluded disabled and invalid IPv4 addresses from WAN IP selection.
- Corrected HTTP status reporting and removed duplicate failure logs.
- Removed the redundant Cloudflare DNS Read token requirement; DNS Edit covers both lookup and updates.
