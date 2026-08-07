# AF_XDP 实战：XDP、UMEM 与 buffer 所有权

> **面试优先级：P2 / 岗位专项。** 先理解 copy 与 zero-copy 不是一回事，以及四个 ring 如何交接 buffer；驱动能力、BPF 权限和 UMEM 细节只在相关岗位深入。

AF_XDP 是 Linux 的高性能 packet socket。XDP 程序可以把指定网卡 queue 的报文重定向到 XSK，应用再通过共享 ring 和 UMEM 收发 packet。

它保留 Linux 驱动与 BPF 控制面，但被 `XDP_REDIRECT` 到 XSK 的 packet 不再继续经过普通 socket、iptables/nftables 等后续网络栈。所谓“与内核共存”不等于每个工具都能看到 fast-path 流量。

## 1. 两种数据模式先别混淆

| 模式 | 数据如何到 UMEM | 能力边界 |
| :--- | :--- | :--- |
| Copy mode | 内核/驱动把 packet 复制到 UMEM | 兼容面较广，但不是零拷贝 |
| Zero-copy mode | 支持的驱动/NIC 直接 DMA 到 UMEM frame | 依赖驱动、queue、frame 配置与 bind 能力 |

`XDP_COPY` 与 `XDP_ZEROCOPY` 是不同的 bind 请求，不应同时 OR 后称为“启用零拷贝”。请求 zero-copy 失败时，是明确报错、回退 copy 还是拒绝启动，应由部署策略决定并在启动日志中暴露。

## 2. 四个 ring 分别交接什么

```mermaid
flowchart LR
    A[Free UMEM Frame] -->|Fill Ring| B[Kernel/Driver RX]
    B -->|RX Descriptor| C[Application]
    C -->|TX Descriptor| D[Kernel/Driver TX]
    D -->|Completion Ring| A
```

1. **Fill Ring**：应用把空闲 UMEM frame 地址交给 RX 路径。提交后应用不能再读写该 frame。
2. **RX Ring**：内核把 `(addr, len, options)` descriptor 交给应用；此时应用可以读取有效范围。
3. **TX Ring**：应用把待发送 frame descriptor 交给 TX 路径；提交后不能修改该 frame。
4. **Completion Ring**：TX 路径通知哪些 frame 不再被设备引用，应用可将其回收到空闲池。

Completion Ring 解决的是**buffer 可复用**，不证明报文已被交换机、对端或交易所看到。线上时间需要 TX hardware timestamp/外部测量，业务接受需要订单协议回报。

## 3. 能力与权限检查

在写 Rust 代码前，先验证：

- 内核开启 BPF/XDP/AF_XDP，发行版没有禁用相关能力。
- NIC 驱动支持 native XDP；zero-copy 还需驱动实现相应 XSK 路径。
- XDP 程序加载、map 更新、锁页和设备操作具备最小必要 capability/权限。
- queue ID 与 NIC channel/RSS 配置一致，不能绑定不存在的 queue。
- `RLIMIT_MEMLOCK`、UMEM 大小、frame 数、ring size 与 cgroup 预算足够。
- 容器/网络 namespace、SR-IOV VF 和 BPF 安全策略允许目标部署。

```bash
ethtool -i eth0
ethtool -l eth0
ip -details link show dev eth0
bpftool feature probe
```

实际命令可能需要权限；生产发布应由受控初始化组件完成，而不是让长期运行的交易进程持有全部 BPF 管理权限。

> 本章 Rust 围栏是**教学骨架**：其中的 `Xsk`、ring、UMEM、frame typestate 和错误类型来自你选定的 AF_XDP wrapper/FFI，并无统一标准库 API，所以标为 `ignore`。验证时应固定 Rust wrapper、内核、驱动和 NIC 固件版本，先做 `cargo check` 与 descriptor/地址边界单测，再在隔离 queue 注入 Fill 耗尽、RX/TX ring 满、`NEED_WAKEUP`、multi-buffer、程序切换失败和设备 reset。

## 4. UMEM 不是普通 `Vec<u8>`

UMEM 需要满足页、frame、headroom、chunk size 和注册生命周期要求。手工 `alloc_zeroed` 后若不保存 `Layout`、不实现 Drop 或不检查对齐，很容易泄漏或 UB。

更安全的 Rust 设计是让已映射内存、注册 socket 和 rings 由一个 RAII owner 统一管理：

```rust,ignore
struct XskUmem {
    mapping: MmapRegion,
    registration: UmemRegistration,
    free_frames: FramePool,
}

impl XskUmem {
    fn frame_mut(&mut self, id: OwnedFreeFrame) -> &mut [u8] {
        // OwnedFreeFrame 证明此 frame 当前不属于 Fill/RX/TX/NIC。
        self.mapping.checked_frame(id)
    }
}
```

可用类型表达 ownership：

```text
FreeFrame -> FillOwned -> RxOwned -> FreeFrame
FreeFrame -> AppTxOwned -> TxOwned -> Completion -> FreeFrame
```

这样能减少同一 frame 同时进入 Fill 与 TX、TX 前被修改、RX 引用活过 refill 等错误。

## 5. XDP 程序与 XSKMAP

典型流程：

1. 创建 UMEM 与 AF_XDP socket。
2. 绑定到 `(ifindex, queue_id)`，明确 copy 或 zero-copy 模式。
3. 创建/复用 XSKMAP，把 queue key 指向对应 socket fd。
4. 加载 XDP 程序；匹配流量执行 `bpf_redirect_map`，其余流量 `XDP_PASS`。
5. 预填 Fill Ring 后再宣告接收路径 ready。

```rust,ignore
match classify(&packet) {
    MarketData => redirect_to_xsk(queue_id),
    Management => XdpAction::Pass,
    Invalid => XdpAction::Drop,
}
```

更新 XDP 程序或 XSKMAP 时要设计原子切换与失败回滚。程序加载成功但 map 尚未就绪，可能把目标流量 redirect 到空入口并丢弃。

## 6. RX 循环与 refill

```rust,ignore
fn process_rx(xsk: &mut Xsk, umem: &mut XskUmem) -> Result<(), RxError> {
    let descriptors = xsk.rx.peek(MAX_BURST);

    for descriptor in descriptors {
        let frame = umem.take_rx_frame(descriptor)?;
        parse_packet(frame.bytes())?;
        umem.recycle_to_fill(frame)?;
    }

    xsk.rx.release(descriptors.len());
    refill_fill_ring(xsk, umem)?;
    Ok(())
}
```

注意：

- descriptor `addr/len` 必须验证在 UMEM 和 frame 边界内。
- multi-buffer packet 能力依赖内核/驱动/API；不能默认一包永远一个 frame。
- Fill Ring 长期不足会让 RX 无 buffer，packet 仍可能丢失。
- 应用处理慢、RX Ring/CQ 满、NIC queue 溢出也不会被“zero-copy”自动解决。

## 7. TX、kick 与 Completion

应用写入 TX descriptor 后，某些模式需要 `sendto`/poll 等 syscall kick 内核，尤其当 ring flags 表示 `NEED_WAKEUP`。不能统一说 busy loop 下永远不需要 syscall。

```rust,ignore
let submitted = xsk.tx.submit(descriptors)?;
if xsk.tx.needs_wakeup() {
    xsk.kick_tx()?;
}

for completed_addr in xsk.completion.consume() {
    // 到这里才把 frame 归还空闲池；不等同于对端收到。
    umem.reclaim_tx(completed_addr)?;
}
```

TX ring 满时需要有界 backpressure。订单数据不能无限重试并悄悄变旧；记录 message age，并在超过风险预算时停止或降级。

## 8. Busy poll 不是把超时设成 0

`SO_BUSY_POLL` 的值通常表示内核忙轮询预算；0 一般表示禁用，而不是“一直轮询”。`SO_PREFER_BUSY_POLL`、NAPI budget、epoll busy poll 等能力会随内核与驱动变化，还可能需要 capability。

调优时同时考虑：

- NAPI ID 与应用线程是否稳定对应目标 queue。
- IRQ、应用、busy-poll 线程和 NUMA 是否对齐。
- poll budget 是否导致其他 queue/控制任务饥饿。
- CPU、功耗、P50/P99.99 与丢包的共同变化。

用户态自己不断检查 RX ring 也是 busy loop，但 NIC 到 ring 的推进仍取决于 XDP/驱动/NAPI 路径，不能等同于 DPDK PMD。

## 9. 可观测性边界

- XDP redirect 发生在网络栈很早的位置，普通 socket/tcpdump tap 点可能看不到 redirect 后的流量。
- `iptables`/nftables 通常不处理已在 XDP 层 redirect/drop 的 packet。
- 应同时记录 XDP action、XSKMAP miss、Fill/RX/TX/Completion ring、NIC drop 和应用 sequence gap。
- 发布新 BPF 程序前保存旧 program/map，支持原子替换和回滚。

## 10. 选型表

| 维度 | AF_XDP | DPDK | 内核 Socket + Busy Poll |
| :--- | :--- | :--- | :--- |
| 驱动路径 | Linux XDP/驱动 | 用户态 PMD | Linux 网络栈 |
| Zero-copy | 依赖 NIC/驱动/queue | 典型 PMD 路径支持 DMA mbuf | 取决于具体 API |
| 设备接管 | 可按流/queue redirect | 常绑定设备/VF 给 DPDK | 无 |
| 内核工具可见性 | fast path tap 点受限 | 需专门 telemetry/mirror | 最完整 |
| 权限 | BPF/XDP、memlock、queue | VFIO/IOMMU、hugepage | 相对较少 |
| 应用责任 | frame/ring、L2+协议 | mbuf/queue、L2+协议 | framing/业务协议 |

## 11. 面试追问

### Q1：AF_XDP 是否一定 zero-copy？

不是。它支持 copy 和 zero-copy 两种模式。zero-copy 需要 NIC 驱动和配置支持；部署必须检查实际 bind 模式，不能静默把 fallback 当成功。

### Q2：Completion Ring 代表报文已经发出去了吗？

它主要表示对应 TX UMEM frame 可由应用回收，即设备/驱动不再引用。线上可见性和对端业务处理需要其他证据。

### Q3：AF_XDP 是否与 tcpdump、iptables 完美共存？

不。设备仍由 Linux 驱动管理，但被 XDP redirect 的 fast-path packet 不继续走普通协议栈；工具能否看到取决于 tap 点与 XDP action。应设计 BPF/ring/NIC telemetry 和端口镜像。

## 12. 总结

AF_XDP 在 Linux 驱动与用户态 packet ring 之间提供了灵活折中，但性能和语义都取决于内核、驱动、XDP 程序、queue 与 UMEM 生命周期。它不是默认最佳方案；只有在能力探测、权限收敛、ring 背压和故障回滚都清楚时才适合上线。
