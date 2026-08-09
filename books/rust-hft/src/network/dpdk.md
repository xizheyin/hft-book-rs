# DPDK 集成：把 NIC 数据面交给用户态

DPDK（Data Plane Development Kit）提供 Poll Mode Driver、mbuf/mempool、ring 与设备抽象，让应用批量管理 NIC Rx/Tx queue。它可能降低每包开销和调度抖动，但并非所有 Rust HFT 系统都需要，也不存在脱离硬件与负载的固定延迟/吞吐保证。

选择 DPDK 意味着同时接管更多责任：设备绑定、DMA 内存、协议处理、CPU、观测、升级和故障恢复。

## 1. DPDK 改变了哪条路径

```mermaid
flowchart LR
    A[NIC Rx Queue] -->|DMA| B[DPDK Mempool / mbuf]
    B --> C[PMD rx_burst]
    C --> D[Rust Parser / Engine]
    D --> E[PMD tx_burst]
    E --> F[NIC Tx Queue]
```

- **VFIO/UIO**：让用户态进程访问设备资源。生产环境通常优先评估具备 IOMMU 隔离的 VFIO，而不是默认使用保护较弱的 UIO。
- **Mempool/mbuf**：预分配 packet buffer 和 metadata，减少热路径动态分配。
- **PMD**：用户态轮询 queue 并批量收发，不依赖通用 socket 数据路径。
- **Hugepage**：可减少 TLB 压力并满足 DMA 映射需求；2MB/1GB 选择取决于平台、容量和运维方案。

轮询通常持续占用一个逻辑 CPU，但部分 PMD/事件模式也支持中断或自适应策略。是否使用纯 busy loop 是设计选择，不是 DPDK 定义本身。

## 2. 上线前先过能力矩阵

| 项目 | 要确认什么 | 不满足时的后果 |
| :--- | :--- | :--- |
| NIC/PMD | 型号、固件、queue、RSS、timestamp、offload | 功能缺失或行为不同 |
| PCIe/NUMA | link 宽度、NIC node、CPU/内存位置 | 跨 NUMA 与带宽抖动 |
| IOMMU/VFIO | group 隔离、设备节点、最小权限 | DMA 隔离不足或无法绑定 |
| 内存 | hugepage、socket memory、mempool 数量 | 启动失败或 burst 时耗尽 |
| OS/运维 | 管理口、监控、崩溃后重新绑定 | 失联或无法快速回滚 |
| Rust FFI | DPDK ABI、bindgen/封装版本、unsafe 审计 | 布局错配、double free、UB |

设备绑定给 DPDK 后，内核网络接口通常不再按原方式可用。管理流量应走独立 NIC/VF，发布脚本要能验证绑定状态并安全回滚。

> 本章 Rust 围栏都是**教学骨架**，依赖 DPDK C 库、生成的 FFI、项目自定义 RAII wrapper、hugepage/VFIO 和真实 NIC，因此统一标为 `ignore`。落地时须锁定 DPDK/PMD/bindgen/固件版本，先运行 `cargo check`、C/Rust ABI 与结构布局测试，再在隔离端口验证 EAL 失败回滚、multi-segment mbuf、部分 TX、mempool 耗尽、设备 reset 和 shutdown drain。

## 3. EAL 与初始化边界

EAL（Environment Abstraction Layer）初始化逻辑 CPU、内存、PCI 设备和进程模型。它不是“调用一次就结束”的小函数：参数决定 NUMA、主/从进程、IOMMU 地址模式和设备探测。

```rust,ignore
fn init_eal(args: &[&str]) -> Result<Eal, DpdkError> {
    // 1. CString 必须一直活到 rte_eal_init 返回，且不能含内部 NUL。
    // 2. argv 指针必须可变且布局符合 C ABI。
    // 3. 检查返回值：负数是失败，非负值表示 DPDK 消费的参数数量。
    // 4. 初始化成功后的全局资源用 RAII guard 管理 shutdown 顺序。
    Eal::new(args)
}
```

Rust wrapper 应把“已初始化、port 已配置、queue 已启动”编码成不同状态类型，避免在错误阶段调用收发 API。

## 4. mbuf 所有权：最容易出现 UB 的地方

`rte_mbuf` 同时描述 payload、长度、segment 链、offload flags、port 和 timestamp metadata。不要把一个裸指针简单包装成无限生命周期的 `&[u8]`。

```rust,ignore
fn handle_burst(port: u16, queue: u16) {
    let mut raw = [std::ptr::null_mut::<rte_mbuf>(); 32];

    loop {
        let received = unsafe {
            rte_eth_rx_burst(port, queue, raw.as_mut_ptr(), raw.len() as u16)
        } as usize;

        for ptr in &raw[..received] {
            // from_rx_owned 检查非空，并取得“必须归还 mempool 或转移给 TX”的所有权。
            let packet = unsafe { OwnedMbuf::from_rx_owned(*ptr) };
            parse_segments(packet.segments())?;
            // 未转发时 Drop 归还；发送成功时所有权转给 TX reclaim 路径。
        }
    }
}
```

需要显式处理：

- `data_len` 只是当前 segment 长度，`pkt_len` 才是整个 packet；包可能跨多个 segment。
- `data_off + data_len` 必须位于实际 buffer 边界内。
- VLAN/checksum/RSS/timestamp 可能在 metadata，而不在你期望的线缆字节位置。
- 引用不能活过 mbuf free、refill 或 TX ownership transfer。
- clone/refcnt、indirect mbuf 与 external buffer 各有不同回收规则。

协议解析应从经过验证的 byte slice 显式处理长度、对齐和 endian，不要把 packet pointer 直接转为 Rust struct 引用。

## 5. Rx 与 Tx 的“完成”不是一回事

### 5.1 `rte_eth_rx_burst`

返回 `n` 表示应用取得前 `n` 个 RX mbuf 的处理责任。它表明 packet 已进入这些 buffer，并不等于函数返回时刻就是 wire arrival。若需要到达时刻，应确认 NIC/PMD 是否提供 RX hardware timestamp，以及 timestamp 对应的 clock domain。

### 5.2 `rte_eth_tx_burst`

```rust,ignore
let sent = unsafe {
    rte_eth_tx_burst(port, queue, packets.as_mut_ptr(), packets.len() as u16)
} as usize;

// [0..sent] 的所有权已经转给 TX 路径，不能立刻修改或 free。
// [sent..] 未被接受，仍归应用；可有界重试、排队或丢弃。
let unsent = &mut packets[sent..];
handle_backpressure(unsent)?;
```

`sent` 只表示多少 descriptor 被 queue 接受，不证明报文已上网线。对应 mbuf 通常在 PMD 清理完成 descriptor 后才回到 mempool；TX timestamp 才更接近实际发送时间，交易所 ACK 才表示业务接受。

对订单路径，无界重试可能把旧订单排很久。必须定义 queue 满时的风险策略、消息 age 上限和 telemetry。

## 6. 批处理：吞吐和首包等待的取舍

固定 burst size 32 只是常见示例，不是最佳值：

- 更大 burst 可以摊薄函数调用和 descriptor 管理成本。
- 等待凑 batch 会增加首包延迟。
- 一次处理太多 RX 可能饿死 TX completion、timer 和控制事件。

常用策略是“最多 N 个、当前有多少就处理多少”，并给周期任务设置明确预算。用真实 microburst 扫描 batch size，比较 P50 至 P99.99、drop、cycles/packet 与 queue 深度。

## 7. CPU、NUMA 与内存调优

### 7.1 CPU 规划

- PMD 线程通常绑到专用物理核，避开 SMT sibling 的无关任务。
- IRQ、RCU、监控等放在 housekeeping core。
- `isolcpus` 不是强制要求；cpuset/cgroup、IRQ affinity 和调度策略也可构造隔离环境。
- 用 `cpu-migrations`、interrupts 和尾延迟验证，而不是只检查启动参数存在。

### 7.2 NUMA

port/queue、mempool 和处理线程尽量位于 NIC 所在 node。EAL socket memory、first touch、hugepage 挂载点和 PCIe 拓扑必须一起检查。

### 7.3 Prefetch 与 DDIO

软件 prefetch 可能隐藏内存延迟，也可能污染 cache 或预取根本用不到的包。DDIO 行为取决于 CPU 平台、BIOS 和资源竞争，不能简单描述为“确保 DMA 直接写 L3”。两者都应通过硬件计数器和端到端基准验证。

## 8. DPDK 不会替你实现的功能

使用 raw packet path 后，团队需要自己或通过成熟用户态协议栈提供：

- Ethernet/VLAN、ARP/IPv6 ND。
- IP 分片策略、ICMP 与 PMTU。
- UDP 组播 membership、A/B 仲裁和 gap recovery。
- 若使用 TCP：拥塞控制、重传、窗口、TIME_WAIT、SACK 和安全更新。
- ACL、防火墙、路由、可观测性和故障注入。

“能发出一个 TCP 包”与“拥有可上线的 TCP 栈”差距很大。订单入口通常更重视协议正确性与恢复，不应为了旁路而仓促重写。

## 9. 选型对比

| 需求 | DPDK | AF_XDP | 内核 Socket/Busy Poll |
| :--- | :--- | :--- | :--- |
| 直接管理多 queue/mbuf | 强 | 中等，依赖 XDP/驱动 | 弱 |
| 保留内核网络接口 | 通常需分离设备/VF | 较容易共存 | 完整保留 |
| 跨 NIC 支持 | 取决于 PMD | 取决于 XDP zero-copy 驱动 | 取决于内核驱动 |
| 权限与部署 | VFIO/hugepage/设备绑定 | BPF/XDP/UMEM/queue | 相对简单 |
| 协议栈责任 | 多由应用承担 | redirect 部分由应用承担 | 内核承担 |
| 调试与抓包 | 需 mirror/telemetry | tap 点需设计 | 工具成熟 |

## 10. 代码推演方法：mbuf 所有权与 burst 返回值

1. **为每个 mbuf 标唯一所有者**：mempool、应用 RX、应用处理、TX queue 或回收阶段只能选一个；跨线程时再标经过哪条 ring。
2. **逐次推演 `rx_burst`**：返回 `n` 后只有前 `n` 个数组槽有效；应用对丢弃包立即释放，对转发包完成必要头部检查与长度校验。
3. **逐次推演 `tx_burst`**：若请求发送 `m` 个只返回 `n`，前 `n` 个转移给 PMD，后 `m-n` 个仍归应用，必须重试、排队或释放。
4. **加入多段与分片**：检查 `pkt_len`、`data_len`、segment 链和 offload 元数据；不能假定所有包都在单个连续 buffer。
5. **验算守恒与活性**：mempool 可用数 + 所有在途 mbuf 数应守恒；压力结束后池应回到基线；任何错误路径都恰好释放一次。

常见陷阱：批量 API 部分成功仍释放全部；把 TX queue 接受当线上可见；忽略 NUMA 远端内存；只测最大 batch 的吞吐而不测首包等待；旁路后忘记 ARP、分片、重组和协议恢复责任。

## 11. 面试追问

### Q1：为什么 DPDK 快？

它通过预分配 mbuf、批量收发、PMD 轮询和更直接的 queue 控制减少通用 per-packet 工作与调度抖动。收益大小取决于包率、batch、NIC/NUMA 和应用处理，不是一个固定微秒数。

### Q2：`tx_burst` 返回 N 表示什么？

表示前 N 个 mbuf 被 TX queue 接受并转移所有权；剩余 mbuf 仍归应用。它不表示线上可见或对端收到，buffer 也要等 PMD reclaim/completion 规则后才能复用。

### Q3：Rust 能把 DPDK 变安全吗？

可以用 RAII、生命周期和 typestate 封装绝大多数调用面，但 FFI、DMA、共享 ring 和 C ABI 仍是 unsafe 边界。安全性取决于 wrapper 是否正确表达所有权、segment、并发和 shutdown 契约。

## 12. 总结

DPDK 是高包率用户态数据面的强大工具，但不是万能答案。只有当内核 socket/AF_XDP 等方案达不到明确 SLA，团队又能承担设备、协议栈、权限与运维责任时，它才是合适选择。
