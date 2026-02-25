# 内存布局与缓存效率 (Memory Layout & Cache Efficiency)

在高频交易中，如果你不关心数据在内存中的布局，你就无法掌控系统的延迟。现代 CPU 是极度依赖缓存（Cache）的机器。一次 L1 Cache 命中仅需 4 个时钟周期，而一次主存（DRAM）访问可能需要 300+ 个周期。这种巨大的鸿沟意味着：**内存布局决定性能**。

本章将探讨如何利用 Rust 的底层控制能力，编写对 CPU 缓存友好的代码。

## 1. 理论背景 (Theory & Context)

### 1.1 缓存行 (Cache Line)
CPU 并不是按字节从内存读取数据，而是按块（Block）读取，这个块称为缓存行。在常见的 x86_64 架构上，缓存行大小通常为 **64 字节**。

这意味着，当你访问结构体的一个字段时，CPU 会将该字段周围的 64 字节一并加载到 L1 Cache 中。利用这一特性，我们可以极大提升数据访问效率（Spatial Locality）。

### 1.2 伪共享 (False Sharing)
当两个线程分别修改位于同一个缓存行中的不同变量时，尽管逻辑上它们互不干扰，但在硬件层面，这两个变量所在的缓存行会不断在两个核心的私有 L1 Cache 之间来回失效和传输。这种现象称为伪共享，会导致严重的性能下降。

## 2. 核心实现：控制结构体布局 (Struct Layout)

Rust 默认不保证结构体字段的内存顺序（除非使用 `#[repr(C)]`），编译器可能会重排字段以减少 padding。但在 HFT 中，我们需要精确控制。

### 2.1 填充与对齐 (Padding & Alignment)

为了避免跨越缓存行边界（这会导致两次内存访问），我们需要对关键数据结构进行对齐。

```rust
use std::mem;

// 假设我们有一个高频更新的计数器
// 为了避免 False Sharing，我们强制将其对齐到 64 字节
#[repr(align(64))]
struct AlignedCounter {
    value: u64,
}

// 验证对齐
fn check_alignment() {
    assert_eq!(mem::align_of::<AlignedCounter>(), 64);
    assert_eq!(mem::size_of::<AlignedCounter>(), 64); // 8 bytes data + 56 bytes padding
}
```

### 2.2 紧凑布局 (Compact Layout)
对于大量的只读数据（如历史行情），我们希望尽可能紧凑，以提高缓存密度。

```rust
// 不良布局：包含大量 padding
struct BadOrder {
    id: u64,        // 8 bytes
    is_buy: bool,   // 1 byte
    // padding: 7 bytes
    price: f64,     // 8 bytes
}

// 紧凑布局
#[repr(packed)] // 警告：直接访问 packed 字段引用是 unsafe 的
struct PackedOrder {
    id: u64,
    price: f64,
    is_buy: bool,
}
```

#### 什么时候使用 `#[repr(packed)]`？

*   **网络协议解析**: 交易所发送的二进制数据包通常是紧凑的（没有 Padding）。你需要直接将 `&[u8]` 强转为 `&PacketStruct`，此时必须用 `packed`。
*   **海量冷数据存储**: 如果你需要存储 10 亿条历史订单，且不常访问，节省 30% 的内存可能意味着省下一台服务器。

#### 什么时候 **绝对不要** 使用？

*   **高频计算的热点数据**: 访问未对齐的内存（Unaligned Access）在 x86 上会导致额外的 CPU 周期（可能跨越两个缓存行），在 ARM 上甚至直接 Crash。
*   **原子操作**: `AtomicU64` 等原子类型必须对齐，否则会导致 panic 或未定义行为。

> **最佳实践**: 在 HFT 中，除非是为了解析网络包，否则 **手动排列字段顺序**（将 `u64` 放前面，`u8` 放后面）来消除 Padding，而不是使用 `packed`。这样既紧凑又对齐。

### 2.3 数组结构 vs 结构数组 (SoA vs AoS)

- **AoS (Array of Structures)**: `[Order; N]`。符合直觉，但在只访问部分字段（如只遍历价格计算均价）时，缓存利用率低。
- **SoA (Structure of Arrays)**: `struct Orders { prices: [f64; N], ids: [u64; N] }`。SIMD 友好，缓存利用率高。

```rust
// SoA 示例：高性能订单簿快照
struct OrderBookSoA {
    prices: Vec<f64>,
    quantities: Vec<u32>,
    ids: Vec<u64>,
}

impl OrderBookSoA {
    // 极度缓存友好，且易于自动向量化 (SIMD)
    fn average_price(&self) -> f64 {
        let sum: f64 = self.prices.iter().sum();
        sum / self.prices.len() as f64
    }
}
```

## 3. 性能分析 (Performance Analysis)

我们通过基准测试来验证缓存友好的 SoA 布局与普通 AoS 布局在遍历求和操作上的性能差异。

### 3.1 基准测试代码

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

struct OrderAoS {
    price: f64,
    qty: u32,
    id: u64,
    padding: [u8; 40], // 模拟大结构体
}

struct OrderSoA {
    prices: Vec<f64>,
    qtys: Vec<u32>,
    ids: Vec<u64>,
}

fn bench_memory_layout(c: &mut Criterion) {
    let size = 1_000_000;
    
    // Setup AoS
    let aos: Vec<OrderAoS> = (0..size).map(|i| OrderAoS {
        price: i as f64,
        qty: i as u32,
        id: i as u64,
        padding: [0; 40],
    }).collect();

    // Setup SoA
    let soa = OrderSoA {
        prices: (0..size).map(|i| i as f64).collect(),
        qtys: (0..size).map(|i| i as u32).collect(),
        ids: (0..size).map(|i| i as u64).collect(),
    };

    let mut group = c.benchmark_group("Memory Layout");
    
    group.bench_function("AoS Sum", |b| b.iter(|| {
        // Cache Miss 严重：每次读取 price 都要跳过 56 字节的无关数据
        aos.iter().map(|o| o.price).sum::<f64>()
    }));

    group.bench_function("SoA Sum", |b| b.iter(|| {
        // Cache Hit 极高：连续读取 f64，预取器（Prefetcher）工作完美
        soa.prices.iter().sum::<f64>()
    }));
    
    group.finish();
}
```

### 3.2 预期结果

在典型的现代 CPU (如 Intel i9 或 AMD Ryzen) 上，**SoA 版本通常比 AoS 版本快 3-10 倍**。

- **AoS**: 每次迭代加载 64 字节缓存行，但只使用了其中的 8 字节 (price)。有效带宽利用率仅 12.5%。
- **SoA**: 每次加载 64 字节缓存行，包含 8 个连续的 price。有效带宽利用率 100%。

### 3.3 硬件预取器 (Hardware Prefetcher)

SoA 的胜利不仅仅是因为数据密度。**硬件预取器** 是关键。

CPU 有专门的电路来检测内存访问模式。当你按顺序访问 `prices[0], prices[1], prices[2]...` 时，预取器会立刻识别出这个线性模式，并提前将 `prices[3], prices[4]...` 从主存拉取到 L1 Cache。

- **SoA**: 完美的线性访问。预取器工作效率 100%。
- **AoS**: 跳跃式访问 (`addr`, `addr+56`, `addr+112`...)。虽然现代预取器也能识别步长（Stride Prefetcher），但效率远不如纯线性访问高，且浪费了宝贵的内存带宽加载无用的 padding。

## 4. 高级话题：Huge Pages 与 TLB (Translation Lookaside Buffer)

在极度优化的 HFT 系统中，除了 CPU 缓存 (L1/L2/L3)，还有一个经常被忽视的瓶颈：**TLB**。

### 4.1 什么是 TLB？

CPU 使用虚拟地址，而内存使用物理地址。每次访问内存，CPU 都需要查表（页表）进行转换。为了加速这个过程，CPU 有一个专门的缓存叫 TLB。

- **默认页大小**: Linux 默认使用 **4KB** 的页。
- **TLB 容量**: 典型的 L1 TLB 只有 64 个条目（指令）和 100 个条目（数据）。L2 TLB 可能有 1500 个。

**问题**: 如果你的程序频繁访问 1GB 的随机内存，你需要 $1GB / 4KB = 262,144$ 个页表项。TLB 根本装不下。结果是每次内存访问都会触发 **TLB Miss**，导致额外的内存延迟（通常几十纳秒）。

### 4.2 Huge Pages (大页)

解决方案是使用 **Huge Pages**。在 x86_64 上，标准大页是 **2MB**（还有 1GB 的巨型页）。

- **4KB 页**: 覆盖 2MB 内存需要 512 个 TLB 条目。
- **2MB 页**: 覆盖 2MB 内存只需要 **1 个 TLB 条目**。

这极大提高了 TLB 命中率。

### 4.3 实战：在 Rust 中使用 `mmap` 分配大页

要使用大页，通常需要两个步骤：系统配置和代码实现。

#### 步骤 1: 操作系统配置 (System Configuration)

你必须先告诉 Linux 内核预留一部分物理内存作为大页。否则 `mmap` 会失败。

```bash
# 查看当前大页情况
cat /proc/sys/vm/nr_hugepages

# 预留 128 个 2MB 大页（共 256MB 内存）
# 这部分内存会被立即锁定，普通程序无法使用
sudo sysctl -w vm.nr_hugepages=128
```

#### 步骤 2: Rust 代码实现

我们可以使用 `libc` crate 直接调用 `mmap`。

```rust
use std::ptr;
use std::slice;

fn allocate_huge_page() {
    // 2MB 是 x86_64 上默认的大页大小
    const HUGE_PAGE_SIZE: usize = 2 * 1024 * 1024;
    let len = HUGE_PAGE_SIZE;

    unsafe {
        // MAP_HUGETLB (0x40000) 告诉内核我们要大页
        // 注意：如果系统没有预留大页，这里会返回 MAP_FAILED (通常是 ENOMEM)
        let ptr = libc::mmap(
            ptr::null_mut(),
            len,
            libc::PROT_READ | libc::PROT_WRITE,
            libc::MAP_PRIVATE | libc::MAP_ANONYMOUS | libc::MAP_HUGETLB,
            -1,
            0,
        );

        if ptr == libc::MAP_FAILED {
            panic!("mmap failed! Did you run 'sudo sysctl -w vm.nr_hugepages=128'?");
        }

        println!("Successfully allocated 2MB huge page at: {:p}", ptr);

        // 使用 slice 访问这块内存
        let data = slice::from_raw_parts_mut(ptr as *mut u8, len);
        
        // 触发缺页中断 (Page Fault)，内核真正分配物理页
        data[0] = 1; 
        data[len - 1] = 255;

        // 释放内存
        // 注意：在 HFT 生产环境中，通常在程序启动时一次性分配所有内存并常驻，
        // 只有在程序退出或重加载配置时才释放。
        libc::munmap(ptr, len);
    }
}

### 4.4 Rust 风格的 RAII 封装

为了避免手动管理内存导致泄漏，我们应该利用 Rust 的 `Drop` trait 来自动管理大页的生命周期。

```rust
struct HugePageBuffer {
    ptr: *mut u8,
    len: usize,
}

impl HugePageBuffer {
    fn new(size: usize) -> Self {
        // ... mmap implementation ...
        // 略，参考上文 allocate_huge_page 实现
        unsafe {
             let ptr = libc::mmap(
                ptr::null_mut(),
                size,
                libc::PROT_READ | libc::PROT_WRITE,
                libc::MAP_PRIVATE | libc::MAP_ANONYMOUS | libc::MAP_HUGETLB,
                -1,
                0,
            );
            if ptr == libc::MAP_FAILED {
                panic!("HugePage allocation failed");
            }
            HugePageBuffer { ptr: ptr as *mut u8, len: size }
        }
    }
    
    fn as_slice_mut(&mut self) -> &mut [u8] {
        unsafe { std::slice::from_raw_parts_mut(self.ptr, self.len) }
    }
}

impl Drop for HugePageBuffer {
    fn drop(&mut self) {
        unsafe {
            // 当结构体离开作用域时，自动归还大页给操作系统
            libc::munmap(self.ptr as *mut _, self.len);
        }
    }
}
```
```

> **注意**: 在生产环境中，我们通常使用 `HugeTLB` 文件系统或者透明大页 (THP)。但对于延迟敏感的 HFT，**显式分配 (Explicit Allocation)** 是最可控的。

## 5. 常见陷阱 (Pitfalls)

1.  **过度对齐 (Over-alignment)**:
    给每个小对象都加上 `#[repr(align(64))]` 会导致巨大的内存浪费（Fragmentation）。只在存在**伪共享风险**的并发数据结构中使用它。

2.  **过早优化**:
    SoA 使得代码变得复杂（插入、删除操作变慢，因为需要操作多个 Vec）。只有在热路径（Hot Path）且经过 Profiling 确认是瓶颈时才重构为 SoA。

3.  **SIMD 陷阱**:
    即使使用了 SoA，如果循环中有分支跳转（if-else），编译器可能无法自动向量化。尽量保持循环体简单，无分支。

## 5. 延伸阅读

- [CPU Caches and Why You Care](https://www.youtube.com/watch?v=WDIkqP4JbkE) - Scott Meyers 的经典演讲。
- [What Every Programmer Should Know About Memory](https://people.freebsd.org/~lstewart/articles/cpumemory.pdf) - Ulrich Drepper 的必读论文。

---
下一章：[零成本抽象 (Zero-Cost Abstractions)](zero_cost.md)
