# W3 installation source-foundation acceptance

*Date: 2026-07-23*
*Decision: `SOURCE_FOUNDATION_ACCEPT`*
*Scope: dormant source only; not an installed-manager acceptance*

## Accepted identities

```text
f48cdfc77a073a215060331adfdbbd823d3a47b4f1776ac6eba83cb666ace946
  scion/runtime/execution/systemd_acquisition.py
7d6309882b770ae336a63892788e0d3c2105b6b1162dbadc5966f3c566dee34f
  scion/tests/unit/runtime/execution/test_systemd_acquisition.py
7cfdc891f79003e0e155ff4d9350a5410ceb83c8bf34c8ca30708b98ecd27297
  scion/problems/warehouse_delivery/w3_composition.py
7b53893ca3685fef43d650d86bf05b4e05812d2e43d532078654ca80b4af0a65
  scion/tests/unit/problems/warehouse_delivery/test_w3_composition.py
17bbc038f914b7ba3cfe6e6c9f989aa7b1c264f98f2779b4c80211be81a37f60
  pyproject.toml
67421c490123f01f0d85e1bba5e8b485d9650a87e5318dca4b11c000c2549524
  scion/tools/__init__.py
```

The governing root-installation plan is accepted separately at raw SHA
`49196769c0c70f56714791a80e6c683d31d547c5f4e47cc7216ea1b5fda81eb6`.

## Accepted behavior

- The real systemd 255 `InvocationID: ay` manager ABI accepts exactly sixteen
  octets and normalizes them to a 32-character lowercase hex value. Manager
  strings, bool octets, wrong lengths and out-of-range octets fail closed.
- An all-zero manager ID is current pre-start absence and cannot be accepted as
  active lineage or final acquisition.
- `ConfiguredPairReadback` preserves the complete configured-property
  acquisition as canonical bytes, but is explicitly not the future
  loaded-manager receipt.
- Readback reopening requires exact trusted run/closer wiring, validates every
  retained raw property through the acquisition converters, cross-binds unit
  identities and pair digest, and rederives the configured pair.
- The old `acquire_configured_pair()` API remains unchanged.
- Warehouse can derive its exact installation pair from the two accepted
  templates without acquiring or mutating a manager.
- The wheel includes the private W3 tool package and both problem-owned service
  templates as package data.

## Verification

- Python 3.12 and 3.13 focused systemd/Warehouse tests pass with warnings as
  errors.
- The complete Python 3.12 generic execution directory collects exact `1738`
  and passes `1737 / 1 skipped` with warnings as errors.
- A live read-only probe against host systemd `255.4` observed the expected
  16-octet D-Bus array and reproduced the canonical active invocation ID.
- A wheel built from the exact current source patch with the accepted gcc-13,
  CFLAGS and `SOURCE_DATE_EPOCH` recipe contains the W3 tool and both unit
  templates.
- That wheel's native extension is exact SHA
  `3d747973bc2eb3b0f6fda68f288987c7b988820eb24df2ff617aa567071803fc`,
  matching the accepted native record.
- Compileall, Black and `git diff --check` pass.

Independent final reviews report:

```text
systemd ABI/readback review: P0=0 P1=0 P2=0 ACCEPT
V3 boundary/ABI review:      P0=0 P1=0 P2=0 ACCEPT
package/composition review:  P0=0 P1=0 ACCEPT
```

## Remaining boundary

This source foundation does not implement candidate preparation, environment
integrity, root publication, FD-bound mounts, manager mutation, start
authorization or terminal acceptance. No `/var/lib/scion` path, system unit,
mount, nonce or formal invocation was created. Those owners remain the next
implementation slice under the fixed accepted plan.
