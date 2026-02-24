# CPU 亲和性与隔离 (CPU Affinity & Isolation)

在追求微秒级甚至纳秒级延迟的高频交易系统中，操作系统（OS）的调度器往往是最大的不可控因素。默认情况下，OS 会根据负载均衡策略在不同 CPU 核心之间迁移线程，这会导致严重的性能损耗：
1.  **缓存失效 (Cache Thrashing)**：线程迁移后，L1/L2 缓存必须重新预热。
2.  **上下文切换开销 (Context Switch Overhead)**：保存和恢复寄存器状态、刷新 TLB 等操作需要时间。
3.  **不可预测的抖动 (Jitter)**：OS 的后台任务、中断处理或其他进程可能会抢占 CPU，导致处理延迟突然飙升。

为了消除这些不确定性，我们需要接管 OS 的调度决策，通过 **CPU 亲和性 (Affinity)** 将关键线程绑定到特定核心，并通过 **CPU 隔离 (Isolation)** 将这些核心从 OS 调度器中移除。

## 理论背景：NUMA 与缓存架构

### NUMA (Non-Uniform Memory Access)
现代服务器通常是多路（Multi-Socket）架构。每个 CPU Socket 有自己的本地内存。访问本地内存最快，访问远程 Socket 的内存则需要经过互连总线（如 Intel UPI 或 AMD Infinity Fabric），延迟更高且带宽受限。

在 HFT 系统中，我们必须确保：
- 关键线程运行在同一个 Socket 上。
- 关键数据分配在同一个 Socket 的本地内存中。
- 网卡 (NIC) 通过 PCIe 连接到同一个 Socket。

### 缓存层级 (Cache Hierarchy)
- **L1 Cache**: ~32KB, ~4 cycles latency. 它是核心独占的。
- **L2 Cache**: ~256KB - 1MB, ~12 cycles latency. 通常也是核心独占的。
- **L3 Cache (LLC)**: ~几十 MB, ~40 cycles latency. 所有核心共享（在同一 Socket 内）。

如果线程在核心之间迁移，L1/L2 缓存将完全失效。即使迁移到同一 Socket 的另一个核心，L3 缓存可能还在，但 L1/L2 的未命中（Miss）依然代价高昂。

## 核心实现：线程绑核 (Thread Pinning)

在 Rust 中，我们可以使用 `core_affinity` crate 或直接调用 `libc` (pthread_setaffinity_np) 来设置线程亲和性。

### 依赖配置

```toml
[dependencies]
core_affinity = "0.8"
libc = "0.2"
```

### 绑核工具封装

我们需要一个能够感知 NUMA 拓扑的绑核工具。

```rust
use core_affinity::CoreId;
use std::thread;

pub struct CoreManager {
    available_cores: Vec<CoreId>,
}

impl CoreManager {
    pub fn new() -> Self {
        let core_ids = core_affinity::get_core_ids().unwrap();
        println!("Detected {} cores", core_ids.len());
        Self {
            available_cores: core_ids,
        }
    }

    /// 将当前线程绑定到指定核心 ID
    pub fn pin_current_thread(core_id: usize) {
        let core = CoreId { id: core_id };
        let res = core_affinity::set_for_current(core);
        if res {
            println!("Thread pinned to core {}", core_id);
        } else {
            eprintln!("Failed to pin thread to core {}", core_id);
        }
    }
    
    /// 获取 NUMA 节点感知推荐 (简化版，实际需解析 /sys/devices/system/node)
    pub fn get_numa_aware_cores(&self, socket_id: usize) -> Vec<usize> {
        // 在生产环境中，你需要解析 `lscpu` 或 `/sys` 文件系统来获取拓扑
        // 这里假设前 N/2 个核属于 Socket 0
        let total = self.available_cores.len();
        let half = total / 2;
        
        if socket_id == 0 {
            (0..half).collect()
        } else {
            (half..total).collect()
        }
    }
}
```

### 在 HFT 引擎中的应用

通常我们采用 **Thread-per-Core** 模型。

```rust
use std::thread;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

fn main() {
    let running = Arc::new(AtomicBool::new(true));
    
    // 1. 市场数据线程 (Market Data) -> Core 2
    let r_md = running.clone();
    thread::spawn(move || {
        CoreManager::pin_current_thread(2);
        println!("Market Data thread running on Core 2");
        while r_md.load(Ordering::Relaxed) {
            // poll_market_data();
            std::hint::spin_loop();
        }
    });

    // 2. 策略与执行线程 (Strategy & Execution) -> Core 3
    // 它们共享 L3 缓存，且都在 Socket 0
    let r_algo = running.clone();
    thread::spawn(move || {
        CoreManager::pin_current_thread(3);
        println!("Strategy thread running on Core 3");
        while r_algo.load(Ordering::Relaxed) {
            // run_strategy();
            std::hint::spin_loop();
        }
    });

    // 主线程做监控或其他非关键任务
    thread::sleep(std::time::Duration::from_secs(10));
    running.store(false, Ordering::Relaxed);
}
```

## 系统级隔离 (System Isolation)

仅仅在代码中绑核是不够的。如果 OS 仍然在这些核心上调度 SSHD、Cron 或其他后台任务，你的 HFT 线程仍会被抢占。你需要配置 Linux 内核参数来隔离核心。

### 1. `isolcpus` (Isolate CPUs)
这是最基础的隔离参数。它告诉 Linux 调度器：不要将任何进程调度到这些核心上，除非显式绑定。

在 `/etc/default/grub` 中添加：
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash isolcpus=2,3,4,5"
```
然后运行 `update-grub` 并重启。

### 2. `nohz_full` (Full Dynticks)
默认情况下，即使核心上只有一个任务，内核也会通过时钟中断（Tick）每隔几毫秒唤醒一次核心来进行统计和调度检查。对于独占核心的 HFT 线程，这是不必要的干扰。

`nohz_full` 允许核心在只有一个可运行任务时停止时钟中断。

```bash
GRUB_CMDLINE_LINUX_DEFAULT="... isolcpus=2-5 nohz_full=2-5 rcunocbs=2-5"
```

### 3. 中断亲和性 (IRQ Affinity)
网卡中断处理也会抢占 CPU。我们需要将网卡中断绑定到特定的核心（通常是紧邻处理线程的核心，或者专门的 I/O 核心），并避开隔离的核心。

检查中断分布：
```bash
cat /proc/interrupts
```

设置中断亲和性（需要 root 权限，通常由脚本在启动时完成）：
```bash
# 将网卡 eth0 的中断队列绑定到 Core 0
echo 1 > /proc/irq/<irq_num>/smp_affinity
```
通常我们会使用 `irqbalance` 守护进程，但在 HFT 环境中，我们通常会**禁用** `irqbalance` 并手动分配中断。

## 常见陷阱 (Pitfalls)

### 1. 错误地使用了超线程 (Hyper-threading)
超线程（Intel HT / AMD SMT）让一个物理核心显示为两个逻辑核心。它们共享 L1/L2 缓存和执行单元（ALU）。
- **风险**：如果 Core 2 (物理) 对应的逻辑核是 CPU 2 和 CPU 14。如果你把关键线程绑在 CPU 2，而把日志线程绑在 CPU 14，它们会争抢同一个物理核心的执行资源，导致严重的延迟。
- **建议**：在 BIOS 中禁用超线程，或者确保每一对逻辑核心中只使用一个。

### 2. 跨 NUMA 访问
如果你把线程绑在 Socket 0 的核心上，却在 Socket 1 的内存中分配了巨大的 `Vec`，或者网卡插在 Socket 1 的 PCIe 插槽上。
- **检测**：使用 `numastat` 或 `pcm-memory` (Intel PCM)。
- **解决**：使用 `numactl --cpunodebind=0 --membind=0 ./hft_app` 启动程序，确保进程内存分配在本地节点。

### 3. C 状态 (C-States) 省电模式
现代 CPU 会在空闲时进入深层睡眠（C-States）以省电。唤醒需要时间（从几微秒到几百微秒）。
- **解决**：在内核启动参数中添加 `intel_idle.max_cstate=0 processor.max_cstate=1`，强制 CPU 保持在 C0 (Active) 状态。

## 性能验证

我们可以编写一个简单的测试来验证绑核的效果。

```rust
use std::time::Instant;

fn measure_jitter() {
    let mut max_latency = 0;
    let mut total = 0;
    let iterations = 10_000_000;
    
    let start = Instant::now();
    for _ in 0..iterations {
        let t0 = Instant::now();
        // 模拟极小的计算工作
        std::hint::black_box(1 + 1);
        let elapsed = t0.elapsed().as_nanos();
        
        if elapsed > 1000 { // 超过 1us 视为抖动
            // println!("Jitter detected: {} ns", elapsed);
        }
        if elapsed > max_latency {
            max_latency = elapsed;
        }
        total += elapsed;
    }
    let total_time = start.elapsed();
    
    println!("Avg latency: {} ns", total / iterations);
    println!("Max latency: {} ns", max_latency);
}
```

在未绑核且未隔离的机器上，你可能会看到 Max latency 达到 50µs 甚至更高。在正确配置的机器上，它应该稳定在极低的数值（如 < 2µs）。
