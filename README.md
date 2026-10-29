# Cloudflare DDNS for MikroTik RouterOS v7

Monitors a network interface's IPv4 address and updates the configured Cloudflare DNS A records when the address changes.

## Requirements

**Cloudflare API Token:**

- Zone - DNS - Edit
- Access to the configured zones, with an existing A record for each domain

**MikroTik Execution Permissions:**

- `read`, `write`, `policy`, `test`
- The scheduler policy must include all permissions declared by the script.

**Device-mode Settings:**

- `fetch` and `scheduler` must be enabled for scheduled execution
- See the [MikroTik device-mode documentation](https://manual.mikrotik.com/docs/system-information-and-utilities/device-mode/) for configuration details.

## Configuration

Configure the following settings in `cloudflare-ddns.rsc`:

### WAN Interface
```routeros
:local WanInterface "ether1"
```
Set `WanInterface` to the name of the interface to monitor.

### Domain and Credentials
```routeros
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
```

Replace the placeholders with the appropriate values:

- `example.domain.com` - Domain name
- `your_cloudflare_zone_id` - Cloudflare Zone ID
- `your_cloudflare_api_token` - Cloudflare API Token

Example with multiple domains:
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

- **CloudflareProxy**: Enables or disables Cloudflare proxying (orange cloud) for DNS records.
- **CheckCertificate**: Enables TLS certificate validation for API requests. Valid CA certificates are required.
- **TestMode**: Checks the interface IP address without modifying DNS records or the cached IP.

## Installation

### 1. Set Script Permissions

Save the script as `cloudflare-ddns` in `/system script` before configuring permissions.

```routeros
/system script set cloudflare-ddns policy=read,write,policy,test
```

### 2. Create the Scheduler
```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns policy=read,write,policy,test
```

The script first runs after the configured interval has elapsed (5 minutes in this example).

## Tested Environment

MikroTik RB5009UG+S+ running RouterOS 7.25.

## Changes — 2026-10-29

- Fixed retry handling after DNS update failures when the WAN IP remains unchanged or returns to a previous address.
- Fixed IP cache updates in TestMode that caused subsequent DNS updates to be skipped.
- Added protection against concurrent script execution.
- Excluded disabled and invalid IPv4 addresses from WAN IP selection.
- Corrected HTTP status reporting and removed duplicate failure logs.
- Removed the redundant Cloudflare DNS Read token requirement; DNS Edit covers both lookup and updates.
