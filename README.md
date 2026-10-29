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

- Clear the completed IP cache before updating and save it only after all configured domains succeed. Retry after a failure or interruption, even if the WAN IP returns to its previous value.
- Leave the cached WAN IP unchanged in TestMode.
- Update the MikroTik Device-mode documentation link to the new official manual.
- Remove the redundant DNS Read requirement and explicitly set scheduler permissions in the installation example.
- Permission references: [Cloudflare DNS API](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/list/), [RouterOS script permissions](https://manual.mikrotik.com/docs/developer-guides/scripting/#script-permissions). The listed RouterOS policies are the example configuration, not a verified minimum.
- Reduce script and scheduler policies to `read,test` based on the code and [official policy definitions](https://manual.mikrotik.com/docs/cli-reference/user/group/). RouterOS runtime verification is pending.
- Fix HTTP error logging: capture Fetch errors where supported and show `unavailable` when the RouterOS version does not expose the HTTP code. RouterOS runtime verification is pending.
- Ignore disabled or invalid interface addresses, and skip overlapping runs of the installed `cloudflare-ddns` script.
- Check the numeric type of substring search results instead of applying `:len` to positions; keep the existing string-based JSON handling.
