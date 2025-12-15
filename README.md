# Cloudflare DDNS for MikroTik RouterOS v7

Monitors a specific network interface and automatically updates Cloudflare DNS A records when the interface IP address changes.

## Requirements

**Cloudflare API Token:**
- Zone - DNS - Read
- Zone - DNS - Edit

**MikroTik Script Permissions:**
- `read`, `write`, `policy`, `test`

**Device-mode Policies:**
- `fetch` and `scheduler` must be allowed in Device-mode
- See [MikroTik Device-mode documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/93749258/Device-mode) for configuration

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
:local CloudflareProxy false  # Cloudflare proxy (orange cloud)
:local CheckCertificate false # SSL certificate verification
:local TestMode false         # Test mode (no actual updates)
```

- **CloudflareProxy**: Cloudflare proxy (orange cloud) for DNS records
- **CheckCertificate**: SSL certificate validation for API connections (requires valid CA certificates)
- **TestMode**: Test mode (IP checks only, no DNS updates)

## Installation

### 1. Set Script Permissions
```routeros
/system script set cloudflare-ddns policy=read,write,policy,test
```

### 2. Create Scheduler
```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns
```
