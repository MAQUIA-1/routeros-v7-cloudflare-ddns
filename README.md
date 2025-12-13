# Cloudflare DDNS for MikroTik RouterOS v7

Monitors a specific network interface and automatically updates Cloudflare DNS A records when the interface IP address changes.

## Requirements

**Cloudflare API Token:**
- Zone - DNS - Edit
- Zone - Zone - Read

**MikroTik Script Permissions:**
- `read`, `write`, `policy`, `test`

## Configuration

Edit `cloudflare-ddns.rsc` before use:

### WAN Interface
```routeros
:local WanInterface "ether1"
```
Change to your actual WAN interface name.

### Domain and Credentials
```routeros
:local ParamVect {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
```

Replace:
- `example.domain.com` - Your domain name
- `your_cloudflare_zone_id` - Cloudflare Zone ID
- `your_cloudflare_api_token` - Cloudflare API Token

For multiple domains:
```routeros
:local ParamVect {
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
:local CloudflareProxy false  # Enable Cloudflare proxy (orange cloud)
:local TestMode false          # Test mode (no actual updates)
```

## Installation

### 1. Set Script Permissions
```routeros
/system script set cloudflare-ddns policy=read,write,policy,test
```

### 2. Create Scheduler
```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns
```
