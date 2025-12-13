# ===========================================================================
# MikroTik RouterOS v7 - Cloudflare DDNS Updater
# ===========================================================================

# ===========================================================================
# Configuration
# ===========================================================================

# ===== MODIFY: Change WAN interface name to your actual interface =====
:local WanInterface "ether1"

# ===== MODIFY: Change domain, Zone ID, and API token to your actual values =====
:local ParamVect {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}

# ===== OPTIONAL: Enable Cloudflare proxy (true/false) =====
:local CloudflareProxy false

# ===== OPTIONAL: Test mode (true=no actual updates) =====
:local TestMode false

# ===========================================================================
# Script Execution
# ===========================================================================

:global WanIP4Cur
:local WanIP4New

# --- WAN IP Lookup ---
:do {
    :local ipAddressList [/ip address find interface=$WanInterface]
    :if ([:len $ipAddressList] = 0) do={
        :log error "[DDNS] No IP address found on interface $WanInterface"
        :error "IP lookup failed"
    }
    :local ipWithMask [/ip address get [:pick $ipAddressList 0] address]
    :set WanIP4New [:pick $ipWithMask 0 [:find $ipWithMask "/"]]
} on-error={
    :log error "[DDNS] Error occurred while looking up WAN IP"
}

:if ([:len $WanIP4New] = 0) do={
    :error "IP lookup failed"
}

# --- IP Change Detection and Update ---
:do {
    :if ($WanIP4New != $WanIP4Cur) do={

        # IP Validation
        :local isValid false
        :do {
            :if ([:typeof [:toip $WanIP4New]] = "ip") do={
                :set isValid true
            }
        } on-error={
            :set isValid false
        }

        :if ($isValid = false) do={
            :log error "[DDNS] Invalid IP address: $WanIP4New"
            :error "IP validation failed"
        }

        :log warning "[DDNS] WAN IP changed: $WanIP4Cur -> $WanIP4New"

        # Cloudflare DNS Update
        :if ($TestMode = false) do={
            :foreach fqdn,params in=$ParamVect do={
                :local DnsZoneID ($params->"DnsZoneID")
                :local AuthToken ($params->"AuthToken")

                # DNS Record Lookup
                :local queryUrl "https://api.cloudflare.com/client/v4/zones/$DnsZoneID/dns_records\?name=$fqdn&type=A"
                :local queryResult [/tool fetch http-method=get mode=https url=$queryUrl \
                    check-certificate=no output=user as-value \
                    http-header-field="Authorization: Bearer $AuthToken"]

                :if ($queryResult->"status" = "finished") do={
                    :local responseData ($queryResult->"data")
                    :local idPos [:find $responseData "\"id\":\""]

                    :if ([:len $idPos] > 0) do={
                        :local idStart ($idPos + 6)
                        :local idEnd [:find $responseData "\"" $idStart]
                        :local DnsRcrdID [:pick $responseData $idStart $idEnd]

                        # Prepare Proxy Setting
                        :local proxiedValue
                        :if ($CloudflareProxy = true) do={
                            :set proxiedValue "true"
                        } else={
                            :set proxiedValue "false"
                        }

                        # DNS Record Update
                        :local updateUrl "https://api.cloudflare.com/client/v4/zones/$DnsZoneID/dns_records/$DnsRcrdID/"
                        :local CfApiResult [/tool fetch http-method=put mode=https url=$updateUrl \
                            check-certificate=no output=user as-value \
                            http-header-field="Authorization: Bearer $AuthToken,Content-Type: application/json" \
                            http-data="{\"type\":\"A\",\"name\":\"$fqdn\",\"content\":\"$WanIP4New\",\"ttl\":60,\"proxied\":$proxiedValue}"]

                        :if ($CfApiResult->"status" = "finished") do={
                            :log warning "[DDNS] Update successful: $fqdn -> $WanIP4New"
                        } else={
                            :log error "[DDNS] Update failed: $fqdn"
                        }
                    } else={
                        :log error "[DDNS] Record ID not found: $fqdn"
                    }
                } else={
                    :log error "[DDNS] Record lookup failed: $fqdn"
                }

                :delay 1s
            }
        }

        :set WanIP4Cur $WanIP4New

    } else={
        :log info "[DDNS] No IP change detected - Current IP: $WanIP4New"
    }
} on-error={
    :log error "[DDNS] Error occurred during DNS update"
}
