# ===========================================================================
# MikroTik RouterOS v7 - Cloudflare DDNS Updater
# ===========================================================================

# ===========================================================================
# Configuration
# ===========================================================================

# ===== MODIFY: Change WAN interface name to your actual interface =====
:local WanInterface "ether1"

# ===== MODIFY: Change domain, Zone ID, and API token to your actual values =====
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}

# ===== OPTIONAL: Enable Cloudflare proxy (true/false) =====
:local CloudflareProxy false

# ===== OPTIONAL: SSL certificate verification (true/false) =====
:local CheckCertificate false

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
        :log error "[DDNS] IP lookup failed: No IP address found (interface: $WanInterface)"
        :error "IP lookup failed"
    }
    :local ipWithMask [/ip address get [:pick $ipAddressList 0] address]
    :set WanIP4New [:pick $ipWithMask 0 [:find $ipWithMask "/"]]
} on-error={
    :log error "[DDNS] IP lookup failed: Error while retrieving WAN IP address"
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
            :log error "[DDNS] IP validation failed: Invalid IP address format ($WanIP4New)"
            :error "IP validation failed"
        }

        # Log IP change with initial run detection
        :if ([:len $WanIP4Cur] = 0) do={
            :log warning "[DDNS] Initial run detected: Setting IP to $WanIP4New"
        } else={
            :log warning "[DDNS] IP change detected: $WanIP4Cur -> $WanIP4New"
        }

        # Cloudflare DNS Update
        :if ($TestMode = false) do={
            # Convert CheckCertificate boolean to yes/no string
            :local certCheck
            :if ($CheckCertificate = true) do={
                :set certCheck "yes"
            } else={
                :set certCheck "no"
            }

            :foreach fqdn,params in=$DomainConfigs do={
                # Wrap each domain update in error handler to prevent one failure from stopping others
                :do {
                    :local DnsZoneID ($params->"DnsZoneID")
                    :local AuthToken ($params->"AuthToken")

                    # DNS Record Lookup
                    :local queryUrl "https://api.cloudflare.com/client/v4/zones/$DnsZoneID/dns_records?name=$fqdn&type=A"
                    :local queryResult [/tool fetch url=$queryUrl http-method=get check-certificate=$certCheck output=user as-value http-header-field="Authorization:Bearer $AuthToken"]

                    :if ($queryResult->"status" = "finished") do={
                        :local responseData ($queryResult->"data")
                        :local httpStatus ($queryResult->"http-status")

                        # Validate API response success
                        :local successPos [:find $responseData "\"success\":true"]
                        :if ([:len $successPos] = 0) do={
                            :log error "[DDNS] Record lookup failed: $fqdn - API returned error (HTTP $httpStatus)"
                            :local errorsPos [:find $responseData "\"errors\":["]
                            :if ([:len $errorsPos] > 0) do={
                                :local errorsEnd [:find $responseData "]" $errorsPos]
                                :local errorsContent [:pick $responseData $errorsPos ($errorsEnd + 1)]
                                :log error "[DDNS] Record lookup error details: $errorsContent"
                            }
                            :error "API call failed"
                        }

                        # Find result array and extract first record ID
                        :local resultPos [:find $responseData "\"result\":["]
                        :if ([:len $resultPos] = 0) do={
                            :log error "[DDNS] Record lookup failed: $fqdn - Invalid API response structure (missing result array)"
                            :error "Invalid API response structure"
                        }

                        # Search for ID within result array (not before it)
                        :local searchStart ($resultPos + 10)
                        :local idPos [:find $responseData "\"id\":\"" $searchStart]

                        :if ([:len $idPos] > 0) do={
                            :local idStart ($idPos + 6)
                            :local idEnd [:find $responseData "\"" $idStart]
                            :local DnsRecordID [:pick $responseData $idStart $idEnd]

                            # Validate Cloudflare record ID format (32 hex characters)
                            :if ([:len $DnsRecordID] != 32) do={
                                :log error "[DDNS] Record validation failed: $fqdn - Invalid record ID format ($DnsRecordID)"
                                :error "Invalid record ID"
                            }

                            # Prepare Proxy Setting
                            :local proxiedValue
                            :if ($CloudflareProxy = true) do={
                                :set proxiedValue "true"
                            } else={
                                :set proxiedValue "false"
                            }

                            # DNS Record Update
                            :local updateUrl "https://api.cloudflare.com/client/v4/zones/$DnsZoneID/dns_records/$DnsRecordID"
                            :local UpdateApiResult [/tool fetch url=$updateUrl http-method=put check-certificate=$certCheck output=user as-value http-header-field="Authorization:Bearer $AuthToken,Content-Type:application/json" http-data="{\"type\":\"A\",\"name\":\"$fqdn\",\"content\":\"$WanIP4New\",\"ttl\":60,\"proxied\":$proxiedValue}"]

                            :if ($UpdateApiResult->"status" = "finished") do={
                                :local updateData ($UpdateApiResult->"data")
                                :local updateHttpStatus ($UpdateApiResult->"http-status")

                                # Validate update API response success
                                :local updateSuccessPos [:find $updateData "\"success\":true"]
                                :if ([:len $updateSuccessPos] > 0) do={
                                    :log warning "[DDNS] Record update succeeded: $fqdn -> $WanIP4New"
                                } else={
                                    :log error "[DDNS] Record update failed: $fqdn - API returned error (HTTP $updateHttpStatus)"
                                    :local updateErrorsPos [:find $updateData "\"errors\":["]
                                    :if ([:len $updateErrorsPos] > 0) do={
                                        :local updateErrorsEnd [:find $updateData "]" $updateErrorsPos]
                                        :local updateErrorsContent [:pick $updateData $updateErrorsPos ($updateErrorsEnd + 1)]
                                        :log error "[DDNS] Record update error details: $updateErrorsContent"
                                    }
                                    :error "Update API returned failure"
                                }
                            } else={
                                :log error "[DDNS] Record update failed: $fqdn - HTTP request error"
                                :error "Update HTTP request failed"
                            }
                        } else={
                            :log error "[DDNS] Record lookup failed: $fqdn - DNS record not found in zone"
                            :error "DNS record not found"
                        }
                    } else={
                        :log error "[DDNS] Record lookup failed: $fqdn - HTTP request error"
                        :error "Lookup HTTP request failed"
                    }
                } on-error={
                    :log error "[DDNS] Record update failed: $fqdn - Skipping to next domain"
                }

                :delay 1s
            }
        }

        :set WanIP4Cur $WanIP4New

    } else={
        :log info "[DDNS] IP check completed: No change detected (current: $WanIP4New)"
    }
} on-error={
    :log error "[DDNS] DNS update failed: Unexpected error during update process"
}
