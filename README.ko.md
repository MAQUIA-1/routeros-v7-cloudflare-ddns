# MikroTik RouterOS v7용 Cloudflare DDNS

지정한 네트워크 인터페이스의 IP 주소가 바뀌면 Cloudflare DNS A 레코드를 자동으로 갱신합니다.

## 요구사항

**Cloudflare API 토큰:**

- Zone - DNS - Edit 권한
- 설정한 Zone에 접근할 수 있어야 하며, 갱신할 A 레코드가 이미 있어야 합니다.

**MikroTik 실행 권한:**

- `read`, `write`, `policy`, `test`
- 스케줄러 권한은 스크립트에 지정된 모든 권한을 포함해야 합니다.

**Device-mode 정책:**

- 예약 실행을 위해 `fetch`와 `scheduler`가 허용되어 있어야 합니다.
- [MikroTik Device-mode 공식 문서](https://manual.mikrotik.com/docs/system-information-and-utilities/device-mode/)

## 설정

`cloudflare-ddns.rsc`에서 다음 값을 수정합니다.

### WAN 인터페이스

```routeros
:local WanInterface "ether1"
```

실제로 사용하는 WAN 인터페이스 이름을 입력합니다.

### 도메인 및 인증 정보

```routeros
:local DomainConfigs {
    "example.domain.com"={
        "DnsZoneID"="your_cloudflare_zone_id";
        "AuthToken"="your_cloudflare_api_token";
    };
}
```

다음 항목을 실제 값으로 바꿉니다.

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

- **CloudflareProxy**: DNS 레코드의 Cloudflare 프록시 사용 여부.
- **CheckCertificate**: API 연결 시 TLS 인증서 검증 여부. 유효한 CA 인증서가 필요합니다.
- **TestMode**: IP 확인만 수행하며 DNS와 IP 캐시를 변경하지 않습니다.

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

첫 예약 실행은 스케줄러 생성 후 설정된 주기만큼 경과한 시점에 수행됩니다. 위 설정에서는 5분 후입니다.

## 검증 환경

MikroTik RB5009UG+S+, RouterOS 7.25.

## 변경사항 — 2026-10-29

- WAN IP가 그대로일 때 실패한 DNS 갱신을 재시도하지 않던 문제를 수정했습니다. IP가 이전 주소로 돌아온 경우에도 복구합니다.
- TestMode 사용 후 실제 DNS 갱신이 생략되던 문제를 수정했습니다.
- 갱신 작업이 겹쳐 실행되지 않도록 했습니다.
- WAN IP를 선택할 때 비활성·유효하지 않은 인터페이스 주소를 제외합니다.
- 실패 로그에 HTTP 상태 코드를 표시하고 중복 오류 로그를 제거했습니다.
- 필요한 권한을 명확히 했습니다. Cloudflare는 DNS Edit, RouterOS는 `read,write,policy,test`를 사용합니다.
