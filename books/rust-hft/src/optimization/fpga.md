# FPGA 交互 (Rust Bindings)

通用 CPU 即使经过优化，也会受到 PCIe、调度和缓存未命中的影响。对延迟价值足够高、逻辑足够稳定的路径，团队可能评估 FPGA；这不是软件达到某个固定微秒数后的自动“下一步”。

现场可编程门阵列（Field-Programmable Gate Array，FPGA）可以把协议解析、预交易风控和部分执行逻辑实现为确定的数据通路。延迟可能达到亚微秒级，但数字取决于测量边界：线缆到线缆、媒体访问控制层到媒体访问控制层（Media Access Control，MAC）、PCIe 往返和完整行情到发单不能混着比较。

FPGA 内部逻辑通常由硬件描述语言实现；本章从主机软件视角解释 Rust 进程怎样配置设备、提交直接内存访问任务并接收完成通知。

## 理论架构：混合系统 (Hybrid Architecture)

通常我们不会把所有逻辑都放入 FPGA（开发成本过高），而是采用混合架构：

1.  **Fast Path (FPGA)**:
    - 处理 L1 市场数据（过滤、归一化）。
    - 简单的触发策略（如 Sniper, Pegging）。
    - 预交易风控（硬性限额）。
    - 订单发送（FIX/Binary 编码）。
2.  **Slow Path (Rust/CPU)**:
    - 复杂策略计算（机器学习推理、多市场套利）。
    - 仓位管理与对账。
    - 异常处理。
    - 配置更新。

Rust 与 FPGA 的通信通常通过 **PCIe（PCI Express）** 总线，涉及两种主要机制：
- **MMIO (Memory Mapped I/O)**: 用于控制寄存器（配置、状态读取）。
- **DMA (Direct Memory Access)**: 用于大批量数据传输（行情流、订单流）。

## 核心实现：用户态驱动 (Userspace Driver)

需要让用户态直接访问设备时，可以使用 UIO（Userspace I/O，用户态 I/O）或 VFIO（Virtual Function I/O）等 Linux 接口，将 FPGA 的 PCIe BAR（Base Address Register，基址寄存器）空间映射到进程虚拟地址。VFIO 通常还能配合输入输出内存管理单元（Input-Output Memory Management Unit，IOMMU）提供隔离；是否绕过普通内核驱动取决于安全、权限和运维要求，而不只是系统调用成本。

### 1. MMIO：像访问内存一样访问硬件

假设 FPGA 暴露了一个控制寄存器（Bar 0, Offset 0x100），写入 1 表示启动，写入 0 表示停止。

下面代码依赖外部 `memmap2`、`libc` crate、Unix 的 `OpenOptionsExt`，以及真实 UIO 设备/驱动 ABI，因此不作为普通 doctest。把依赖锁入项目后，先用 mock 映射测试 offset/边界逻辑，再在隔离测试机上用厂商寄存器测试设计验证读写；不要在开发机上随意写真实 BAR。

```rust,ignore
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use memmap2::{MmapOptions, MmapMut};

pub struct FpgaDevice {
    bar0: MmapMut,
}

impl FpgaDevice {
    pub fn new(uio_path: &str) -> Self {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_SYNC)
            .open(uio_path)
            .expect("Failed to open UIO device");

        let mmap = unsafe {
            MmapOptions::new()
                .len(4096) // 假设 BAR0 大小
                .map_mut(&file)
                .expect("Failed to mmap BAR0")
        };

        Self { bar0: mmap }
    }

    /// 写入 32 位寄存器
    /// offset 必须是 4 的倍数
    #[inline(always)]
    pub unsafe fn write_reg(&mut self, offset: usize, value: u32) {
        assert_eq!(offset % std::mem::align_of::<u32>(), 0);
        let end = offset
            .checked_add(std::mem::size_of::<u32>())
            .expect("register offset overflow");
        assert!(end <= self.bar0.len());
        let ptr = unsafe { self.bar0.as_mut_ptr().add(offset).cast::<u32>() };
        // SAFETY: 调用者保证 offset 对应可写 MMIO 寄存器；边界与对齐已检查。
        unsafe { std::ptr::write_volatile(ptr, value) };
    }

    /// 读取 32 位寄存器
    ///
    /// # Safety
    /// 调用者必须确认 offset 对应允许读取的寄存器，并理解读取副作用。
    #[inline(always)]
    pub unsafe fn read_reg(&self, offset: usize) -> u32 {
        assert_eq!(offset % std::mem::align_of::<u32>(), 0);
        let end = offset
            .checked_add(std::mem::size_of::<u32>())
            .expect("register offset overflow");
        assert!(end <= self.bar0.len());
        let reg_ptr = unsafe { self.bar0.as_ptr().add(offset).cast::<u32>() };
        // SAFETY: offset 对应可读 MMIO 寄存器；边界与对齐已检查。
        unsafe { std::ptr::read_volatile(reg_ptr) }
    }
}
```

`volatile` 只阻止编译器删除或合并这次访问，不自动提供跨线程同步、DMA 可见性或平台所需的设备内存屏障。寄存器宽度、端序、读写副作用和屏障顺序必须来自 FPGA/驱动 ABI（Application Binary Interface，应用二进制接口）。

### 2. 零拷贝 DMA 环形缓冲区

对于高吞吐量的行情数据，FPGA 会通过 DMA 直接将数据写入主机的 RAM。我们需要在 Rust 中分配一块对齐的内存，并将其物理地址告诉 FPGA。

普通 `Vec<u8>` 不能直接当 DMA buffer：虚拟地址不等于设备可使用的地址，物理页也不保证连续或已 pin。读取 `/proc/self/pagemap` 再把“物理地址”交给设备既不可靠，也绕开了 IOMMU 隔离。

生产方案通常由内核驱动、VFIO 或厂商 SDK 完成：

1. 分配并 pin DMA 内存。
2. 在 IOMMU 中映射为 IOVA（I/O Virtual Address）。
3. 把 IOVA、长度和 ownership 写入硬件定义的 descriptor。
4. 按 ABI 执行 DMA memory barrier，再更新 producer index/doorbell。
5. 设备完成后读取 completion，并在归还 descriptor 前执行对应 acquire/barrier。

下面是 **DMA provider 接口骨架**，其中 `DmaError` 与具体 region 类型由 VFIO 或厂商驱动封装提供。先用内存 mock 验证 descriptor ownership/ring wrap，再在带 IOMMU 的目标机运行驱动集成测试；不能用普通单元测试宣称 DMA 已正确。

```rust,ignore
// 教学接口：具体实现必须来自经过审查的 VFIO/厂商驱动封装。
trait DmaProvider {
    type Region;

    fn alloc_pinned(&self, len: usize, alignment: usize) -> Result<Self::Region, DmaError>;
    fn iova(region: &Self::Region) -> u64;
}
```

“zero-copy”也不代表没有同步成本。CPU 和 FPGA 仍需通过 descriptor ownership、cache coherency 与 memory ordering 协议移交缓冲区。

## 实战案例：FPGA 辅助的订单发送

在这个场景中，Rust 策略决定下单，但为了节省 PCI 往返时间，我们只发送核心参数（Price, Qty, Side），由 FPGA 填充协议头（FIX/OUCH）并计算校验和。

下面同样是多模块**集成骨架**：`FpgaDevice`、`command_ring`、`driver` 和 `DOORBELL_OFFSET` 必须来自已验证的驱动层。完成实现后，应分别运行 descriptor 编解码单测、mock ring 测试和真实硬件 loopback/抓包测试。

```rust,ignore
#[repr(C, align(64))]
struct FastOrderCmd {
    symbol_index: u16,
    side: u8,
    reserved0: [u8; 5],
    price_le: u64,
    qty_le: u32,
    reserved1: [u8; 44],
}

impl FpgaDevice {
    pub fn send_order(&mut self, cmd: FastOrderCmd) {
        // 1. 把完整 descriptor 写入驱动提供的 DMA command ring。
        // 2. 执行硬件 ABI 要求的 DMA write barrier。
        // 3. 通过合法的 BAR offset 写 producer index/doorbell。
        self.command_ring.push(cmd).expect("bounded ring has capacity");
        self.driver.dma_write_barrier();
        unsafe { self.write_reg(DOORBELL_OFFSET, self.command_ring.tail()) };
    }
}
```

这里用显式 `reserved` 固定 64 字节布局，并在字段名中标出 endian。真实项目还应使用 compile-time size/offset 断言和 Rust/C/RTL 共享 schema。不要把 packed struct 转成 `*const u64` 解引用：地址可能未对齐，而且一次 MMIO 写只发送了结构体的一部分。

## 常见陷阱

1.  **内存序 (Memory Ordering)**: Rust atomic fence 不一定等同于驱动 ABI 要求的 DMA/MMIO barrier；必须按平台与驱动文档实现 descriptor → barrier → doorbell 顺序。
2.  **缓存一致性 (Cache Coherency)**: 一些服务器平台的 DMA coherent，另一些设备/映射模式需要显式 sync。不能把“通常”当契约。
3.  **对齐与边界**: descriptor、DMA buffer、BAR 寄存器都有各自要求，不是统一的 64B 或 4KB。
4.  **错误与超时**: completion 丢失、设备 reset、PCIe AER（Advanced Error Reporting，高级错误报告）、ring wrap 和错误 descriptor 都需要状态机与降级路径。
5.  **风控一致性**: FPGA 与 CPU 两边的限制版本必须原子切换并可审计，不能出现一边已更新、一边仍用旧值。

## 现有生态

- **Xilinx XDMA / QDMA**: 官方提供了 Linux 驱动，Rust 可以通过 `ioctl` 与之交互。
- **VFIO/UIO**: Linux 提供的用户态设备访问机制；VFIO 具备 IOMMU 隔离能力，UIO 更简单但保护能力较弱。

## 做题方法：沿 DMA、队列和完成事件推演

1. **读题画边界**：CPU 用户态、驱动/VFIO、IOMMU、DMA ring、FPGA pipeline 和 NIC/线缆分别标输入输出，说明哪层负责协议与风控。
2. **列 descriptor 状态**：Free→Prepared→Submitted→DeviceOwned→Completed→Free，每个状态允许谁读写 buffer，内存屏障与 doorbell 在哪里。
3. **做容量计算**：按消息率、单条 descriptor/数据字节和最坏服务时间估算在途数与 ring 深度；单位统一并留 burst 余量。
4. **推演异常**：ring 满、DMA fault、设备 reset、completion 丢失/迟到、bitstream 不匹配和主机进程崩溃时，指出停止发送与重新同步步骤。
5. **验算**：descriptor/buffer 数守恒且不重复回收；设备完成、wire timestamp 和交易所 ACK 三种完成不混淆；软件与 FPGA 对协议向量输出逐字节一致。

常见陷阱：把 FPGA 当自动低延迟；CPU 写完 descriptor 未做所需可见性同步就敲 doorbell；completion 当成交回报；忽略 IOMMU/权限和 reset 恢复；固定某场所编码却未绑定协议版本。

## 面试高频问答

### Q1：MMIO 与 DMA 的区别是什么？

MMIO 让 CPU 读写设备寄存器，适合配置、状态和 doorbell；DMA 让设备直接读写主机内存，适合批量数据。低延迟设计常用 DMA ring 放 descriptor，再用一次 MMIO doorbell 通知设备。

### Q2：为什么 `write_volatile` 不够？

它只约束编译器对该访问的优化，不完整约束 CPU、PCIe、DMA 与设备观察顺序。还需要 ABI 规定的 memory barrier、ownership 位和 completion 协议。

### Q3：Rust 在 FPGA host code 中解决了什么、没解决什么？

Rust 能封装资源生命周期、边界、状态机和 FFI，减少 use-after-free 等错误；但 `unsafe` MMIO/DMA、硬件 coherency、IOMMU 配置和 RTL 协议仍需人工证明与硬件测试。

FPGA 开发周期、验证和运维成本很高。是否采用应由完整 wire-to-action 延迟、策略价值、变更频率与失效风险共同决定，而不是只追求一个漂亮的纳秒数字。

## 权威依据

- [Linux 内核：VFIO—Virtual Function I/O](https://docs.kernel.org/driver-api/vfio.html)：说明用户态设备访问、IOMMU 隔离、设备区域映射、中断和 DMA 映射。
- [Linux 内核：IOMMUFD](https://docs.kernel.org/userspace-api/iommufd.html)：说明用户态 I/O 地址空间（IOAS）、I/O 虚拟地址（IOVA）映射与设备绑定。
