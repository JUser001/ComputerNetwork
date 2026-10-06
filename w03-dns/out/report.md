# DNS and CDN measurement

Measurement runs: Network 1 (before move) (2026-10-06T04:16:27Z); Wi-Fi after move (2026-10-06T05:24:41Z)
CNAME table uses the chain collected at **Network 1 (before move)**.

The rule verdict is **yes** only when a CNAME chain exists and its final name has a different registrable domain from the queried site. The third-party column uses known provider zones and ownership context; `unknown` means DNS names alone do not establish ownership.

| Site | Chain length | Final zone | Third party? | Rule verdict |
|---|---:|---|---|---|
| `www.microsoft.com` | 2 | `akamaiedge.net` | yes | yes |
| `www.netflix.com` | 1 | `netflix.com` | no | no |
| `www.adobe.com` | 2 | `akamai.net` | yes | yes |
| `www.cnn.com` | 1 | `fastly.net` | yes | yes |
| `www.apple.com` | 3 | `akamaiedge.net` | yes | yes |
| `www.korea.ac.kr` | 0 | `korea.ac.kr` | no | no |
| `www.stanford.edu` | 1 | `netlifyglobalcdn.com` | yes | yes |
| `www.bbc.co.uk` | 2 | `fastly.net` | yes | yes |
| `www.spotify.com` | 1 | `fastly.net` | yes | yes |
| `www.github.com` | 1 | `github.com` | yes (anycast inference) | no |
| `www.wikipedia.org` | 1 | `wikimedia.org` | no | yes |
| `www.nytimes.com` | 3 | `fastly.net` | yes | yes |

## Steering

- **Network 1 (before move):** 8 of 12 sites answered differently to a different resolver (system, Google, Quad9).
- **Wi-Fi after move:** 8 of 12 sites answered differently to a different resolver (system, Google, Quad9).

Comparing the same resolver across **Network 1 (before move)** and **Wi-Fi after move**, 2 of 12 sites returned different address sets.

Different DNS answers show resolver- or network-dependent steering; they do not by themselves prove that a user was sent to a geographically nearby replica. The rule gets `www.wikipedia.org` wrong: its chain ends in `wikimedia.org`, a different registrable domain, but that is operated by the Wikimedia Foundation rather than a third-party CDN. `www.github.com`'s anycast/third-party status remains an inference, not something established by its DNS chain.
