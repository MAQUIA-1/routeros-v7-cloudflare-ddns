# MikroTik RouterOS v7 - Cloudflare DDNS Updater
# https://github.com/MAQUIA-1/routeros-v7-cloudflare-ddns

# ===========================================================================
# Configuration
# ===========================================================================
# WAN interface selection
:local WanInterface "ether1"
# DNS records and Cloudflare zone credentials
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
# Cloudflare proxy status
:local CloudflareProxy false
# TLS certificate verification
:local CheckCertificate false
# Test mode: disable DNS updates and cache writes
:local TestMode false

# ===========================================================================
# Cloudflare API request handling
:local callApi do={
    :local fetched
    :onerror fetchError,fetchAttrs in={
        :set fetched [/tool fetch url=$requestUrl http-method=$requestMethod \
            check-certificate=$certificateCheck output=user as-value \
            http-header-field=$requestHeaders http-data=$requestData]
    } do={
        :local httpCode ($fetchAttrs->"code")
        :if ([:typeof $httpCode] != "num") do={ :set httpCode "unavailable" }
        :error ("$operation failed: HTTP $httpCode - $fetchError")
    }

    :if (($fetched->"status") != "finished") do={
        :error "$operation failed: Fetch did not finish"
    }

    :local body ($fetched->"data")
    :if ([:typeof [:find $body "\"success\":true"]] = "num") do={
        :return $body
    }

    :local details "Cloudflare did not report success"
    :local errorsStart [:find $body "\"errors\":["]
    :if ([:typeof $errorsStart] = "num") do={
        :local errorsEnd [:find $body "]" $errorsStart]
        :if ([:typeof $errorsEnd] = "num") do={
            :set details [:pick $body $errorsStart ($errorsEnd + 1)]
        }
    }
    :local httpCode ($fetched->"code")
    :if ([:typeof $httpCode] != "num") do={ :set httpCode "unavailable" }
    :error ("$operation failed: HTTP $httpCode - $details")
}

# DNS record synchronization
:local updateDomain do={
    :local api $apiFunction
    :local zoneID ($domainConfig->"DnsZoneID")
    :local token ($domainConfig->"AuthToken")
    :local baseUrl "https://api.cloudflare.com/client/v4/zones/$zoneID/dns_records"
    :local headers "Authorization:Bearer $token,Content-Type:application/json"

    :local lookupBody [$api operation="Record lookup" \
        requestUrl=($baseUrl . "?name=" . $domainName . "&type=A") requestMethod="get" \
        certificateCheck=$certificateCheck requestHeaders=$headers requestData=""]

    :local resultStart [:find $lookupBody "\"result\":["]
    :if ([:typeof $resultStart] != "num") do={
        :error "Record lookup failed: Missing result array"
    }
    :local idStart [:find $lookupBody "\"id\":\"" ($resultStart + 10)]
    :if ([:typeof $idStart] != "num") do={
        :error "Record lookup failed: A record not found"
    }
    :set idStart ($idStart + 6)
    :local idEnd [:find $lookupBody "\"" $idStart]
    :if ([:typeof $idEnd] != "num") do={
        :error "Record lookup failed: Unterminated record ID"
    }
    :local recordID [:pick $lookupBody $idStart $idEnd]
    :if ([:len $recordID] != 32) do={
        :error "Record lookup failed: Invalid record ID length"
    }

    :local payload "{\"type\":\"A\",\"name\":\"$domainName\",\"content\":\"$wanIP\",\"ttl\":60,\"proxied\":$proxyValue}"
    :local updateBody [$api operation="Record update" \
        requestUrl=($baseUrl . "/" . $recordID) requestMethod="put" \
        certificateCheck=$certificateCheck requestHeaders=$headers requestData=$payload]
}

# Main execution
:local run do={
    :global WanIP4Cur

    # Concurrent execution control
    :if ([/system script job print count-only where script="cloudflare-ddns"] > 1) do={
        :log warning "[DDNS] Another instance is running: Skipping this run"
        :return false
    }

    :local addresses [/ip address find where interface=$wanInterface disabled=no invalid=no]
    :if ([:len $addresses] = 0) do={
        :error "No enabled, valid IPv4 address found on $wanInterface"
    }
    :local addressWithMask [/ip address get [:pick $addresses 0] address]
    :local wanIP [:pick $addressWithMask 0 [:find $addressWithMask "/"]]
    :if ([:typeof [:toip $wanIP]] != "ip") do={
        :error "Invalid WAN IPv4 address: $wanIP"
    }

    :if ($wanIP = $WanIP4Cur) do={
        :log info "[DDNS] No IP change: $wanIP"
        :return false
    }
    :if ($testMode = true) do={
        :log info "[DDNS] Test mode: WAN IP $wanIP; DNS and cached IP unchanged"
        :return false
    }
    :if ([:len $domains] = 0) do={
        :error "No domains configured"
    }

    :local certCheck "no"
    :if ($checkCertificate = true) do={ :set certCheck "yes" }
    :local proxyValue "false"
    :if ($cloudflareProxy = true) do={ :set proxyValue "true" }

    :local update $updateFunction
    :local allSucceeded true
    :log info "[DDNS] Synchronizing configured A records to $wanIP"
    # Invalidate the cache to allow retries after incomplete synchronization.
    :set WanIP4Cur ""
    :foreach fqdn,config in=$domains do={
        :onerror domainError in={
            :local updated [$update apiFunction=$apiFunction domainName=$fqdn domainConfig=$config \
                wanIP=$wanIP certificateCheck=$certCheck proxyValue=$proxyValue]
            :log info "[DDNS] Record updated: $fqdn -> $wanIP"
        } do={
            :set allSucceeded false
            :log error "[DDNS] $fqdn - $domainError"
        }
        :delay 1s
    }

    :if ($allSucceeded = true) do={ :set WanIP4Cur $wanIP }
}

:onerror runError in={
    :local completed [$run wanInterface=$WanInterface domains=$DomainConfigs testMode=$TestMode \
        checkCertificate=$CheckCertificate cloudflareProxy=$CloudflareProxy \
        apiFunction=$callApi updateFunction=$updateDomain]
} do={
    :log error "[DDNS] $runError"
}
