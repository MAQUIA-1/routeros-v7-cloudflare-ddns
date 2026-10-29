# Cloudflare DDNS for MikroTik RouterOS v7

Monitors a specific network interface and automatically updates Cloudflare DNS A records when the interface IP address changes.

## Requirements

**Cloudflare API Token:**

- Zone - DNS - Edit
- Access to the configured zones and existing A records

**MikroTik Script Permissions:**

- `read`, `test`
- Set the scheduler policy to match (see Installation).

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
- **CheckCertificate**: SSL certificate validation for API connections (requires valid CA certificates)
- **TestMode**: Test mode (IP checks only, no DNS updates)

## Installation

### 1. Set Script Permissions

These commands assume the script has already been saved as `cloudflare-ddns` in `/system script`.

```routeros
/system script set cloudflare-ddns policy=read,test
```

### 2. Create Scheduler
```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns policy=read,test
```

## Changes — 2026-10-29

- Fixed failed DNS updates not being retried while the WAN IP remains unchanged, including recovery when it returns to a previous address.
- Fixed TestMode causing the next normal run to skip DNS updates.
- Added protection against overlapping update runs.
- Excluded disabled and invalid interface addresses from WAN IP selection.
- Improved failure messages with HTTP status codes and removed duplicate error logs.
- Simplified permissions: Cloudflare DNS Edit covers both lookup and updates; script and scheduler permissions are now `read,test`.
