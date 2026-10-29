# MikroTik RouterOS v7용 Cloudflare DDNS

[English](README.md) | **한국어**

지정한 인터페이스의 **IPv4 주소**가 변경되면 Cloudflare DNS **A 레코드**를 자동으로 갱신합니다. 외부 IP 조회 서비스는 사용하지 않습니다.

## 요구사항

**Cloudflare API 토큰:**

- Zone - DNS - Edit 권한
- 설정된 Zone에 접근할 수 있어야 하며, 각 도메인의 A 레코드가 이미 존재해야 합니다.

**MikroTik 실행 권한:**

- `read`, `write`, `policy`, `test`
- 스케줄러 권한은 스크립트에 지정된 모든 권한을 포함해야 합니다.

**Device-mode 설정:**

- 예약 실행을 위해 `fetch`와 `scheduler`가 활성화되어 있어야 합니다.
- 설정 방법은 [MikroTik device-mode 공식 문서](https://manual.mikrotik.com/docs/system-information-and-utilities/device-mode/)를 참고하세요.

## 설정

`cloudflare-ddns.rsc`에서 다음 항목을 설정합니다.

### WAN 인터페이스

```routeros
:local WanInterface "ether1"
```

`WanInterface`에 주소를 확인할 인터페이스 이름을 지정합니다.

### 도메인 및 인증 정보

```routeros
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
```

다음 예시 값을 실제 설정값으로 바꿉니다.

- `example.domain.com`: 갱신할 도메인 이름
- `your_cloudflare_zone_id`: Cloudflare Zone ID
- `your_cloudflare_api_token`: Cloudflare API 토큰

여러 도메인을 설정하는 예시:

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

### 선택 설정

```routeros
:local CloudflareProxy false
:local CheckCertificate false
:local TestMode false
```

- **CloudflareProxy**: DNS 레코드의 Cloudflare 프록시(주황색 구름) 사용 여부를 설정합니다.
- **CheckCertificate**: API 요청 시 TLS 인증서 검증을 활성화합니다. 유효한 CA 인증서가 필요합니다.
- **TestMode**: DNS 레코드와 IP 캐시를 변경하지 않고 인터페이스의 IP 주소만 확인합니다.

## 설치

### 1. 스크립트 권한 설정

`/system script`에 스크립트를 `cloudflare-ddns`라는 이름으로 저장한 후 권한을 설정합니다.

```routeros
/system script set cloudflare-ddns policy=read,write,policy,test
```

### 2. 스케줄러 생성

```routeros
/system scheduler add name=cloudflare-ddns-scheduler interval=5m on-event=cloudflare-ddns policy=read,write,policy,test
```

스크립트의 첫 예약 실행은 설정된 주기가 경과한 후 수행됩니다. 위 예시에서는 5분 후입니다.

## 검증 환경

RouterOS 7.25를 실행하는 MikroTik RB5009UG+S+.

## 변경사항 — 2026-10-29

- DNS 갱신 실패 시 WAN IP가 그대로이거나 이전 주소로 복귀해도 재시도하도록 수정했습니다.
- TestMode에서 IP 캐시가 변경되어 이후 DNS 갱신이 생략되던 문제를 수정했습니다.
- 스크립트 중복 실행 방지를 추가했습니다.
- WAN IP 선택에서 비활성·유효하지 않은 IPv4 주소를 제외했습니다.
- HTTP 상태 코드 표시를 수정하고 중복 실패 로그를 제거했습니다.
- Cloudflare 토큰의 불필요한 DNS Read 요구사항을 제거했습니다. DNS Edit 권한으로 조회와 갱신을 수행합니다.
