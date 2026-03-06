# CPU 微架构原理 (CPU Microarchitecture)

在高频交易面试中，面试官经常会问：“为什么 if 语句会慢？”或者“什么是分支预测失败？”。如果不理解 CPU 的工作原理，你就无法编写出真正榨干硬件性能的代码。

本章将深入 CPU 内部，解释流水线、分支预测和乱序执行等核心概念。理解这些，是成为 HFT 开发者的第一步。

## 1. 指令流水线 (Instruction Pipeline)

想象一家汽车组装工厂。如果不使用流水线，工人们必须先造完底盘，再装引擎，再装轮胎，最后喷漆，然后才能开始造下一辆车。这显然效率极低。

现代 CPU 也是如此。执行一条指令并不是瞬间完成的，它通常分为以下几个阶段（以经典的 5 级流水线为例）：

1.  **取指 (Fetch, IF)**: 从内存（或 L1 指令缓存）中读取指令。
2.  **译码 (Decode, ID)**: 将指令翻译成 CPU 内部的微操作 (uOps)。
3.  **执行 (Execute, EX)**: ALU 进行计算（加减乘除）。
4.  **访存 (Memory, MEM)**: 读写内存数据。
5.  **写回 (Writeback, WB)**: 将结果写回寄存器。

### 1.1 直观图解：流水线如何工作

假设我们需要执行 3 条独立的指令（A, B, C）。

**无流水线 (Serial Execution):**
每条指令需要 5 个时钟周期。3 条指令总共需要 15 个周期。

```text
Cycle: 1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
Instr A: [IF][ID][EX][MEM][WB]
Instr B:                [IF][ID][EX][MEM][WB]
Instr C:                               [IF][ID][EX][MEM][WB]
```

**有流水线 (Pipelined Execution):**
虽然单条指令的延迟（Latency）没有变（仍然需要 5 个时钟周期），但吞吐量（Throughput）变成了每个周期完成 1 条指令。3 条指令只需要 7 个周期！

```text
Cycle: 1  2  3  4  5  6  7
Instr A: [IF][ID][EX][MEM][WB]
Instr B:    [IF][ID][EX][MEM][WB]
Instr C:       [IF][ID][EX][MEM][WB]
```

### 1.2 流水线气泡 (Pipeline Bubble)

但是，如果下一条指令依赖上一条指令的结果（数据依赖），或者遇到跳转指令（控制依赖），流水线就会停顿。这就像前面的工序卡住了，后面的工序只能空等。这种停顿称为“气泡”。

**示例代码：数据依赖**
```rust
let a = 10;
let b = a + 5; // 依赖 a 的值
```

在执行 `b = a + 5` 的 **Execute** 阶段之前，必须等待 `a = 10` 的 **Writeback** 阶段完成（或者通过 Forwarding 技术提前拿到结果）。如果无法通过 Forwarding 解决，流水线就会出现气泡。

```text
Cycle: 1  2  3  4  5  6  7  8
Instr 1 (a=10): [IF][ID][EX][MEM][WB]
Instr 2 (b=a+5):   [IF][ID] .. .. [EX][MEM][WB]  <-- 气泡 (Bubble)
```

## 2. 分支预测 (Branch Prediction)

这是 HFT 中最常被提及的概念。

当 CPU 遇到一个 `if` 语句（条件跳转）时，它面临一个难题：下一条指令在哪里？是 `if` 块里的代码，还是 `else` 块里的代码？
由于流水线的存在，CPU 不能等待条件判断的结果算出来再决定去哪里取指（那会浪费十几个周期）。

**CPU 必须猜测**。

*   **预测正确**: 流水线继续满负荷运转，几乎没有性能损失。
*   **预测失败 (Misprediction)**: 灾难发生。CPU 必须清空整个流水线中所有已经执行但尚未写回的指令（因为它们是基于错误的路径执行的），重新从正确的地址开始取指。这会导致 **15-20 个时钟周期** 的惩罚。

### 2.1 经典案例：有序数组处理更快

这也是为什么处理有序数组往往比处理乱序数组快得多的原因。

```rust
// 假设 data 是随机的
for &x in data.iter() {
    if x > 128 { // 这个分支很难预测，如果是随机数，预测准确率只有 50%
        sum += x;
    }
}
```

如果 `data` 是有序的（如 `0, 1, 2... 255`），那么前一半全是 `false`，后一半全是 `true`。分支预测器可以轻松达到 100% 的准确率。

### 2.2 无分支编程 (Branchless Programming)

为了避免分支预测失败，我们可以使用数学运算或位运算来替代 `if`。

**有分支写法:**
```rust
let y = if x > 0 { 1 } else { 0 };
```
这会生成跳转指令 (`JMP`, `JNE`)，可能导致流水线清空。

**无分支写法:**
```rust
let y = (x > 0) as i32;
```
这会生成条件传送指令 (`CMOV`) 或利用比较指令的结果直接计算。虽然计算量可能稍大（多执行了一条指令），但它**消除了不确定性**，保证了流水线的顺畅。

### 2.3 Rust 中的优化提示

虽然现代 CPU 的分支预测器非常聪明（使用历史表和感知机算法），但在某些极端情况下，我们可以手动给编译器提示。

```rust
#![feature(core_intrinsics)]
use std::intrinsics::{likely, unlikely};

if unsafe { likely(x > 0) } {
    // 编译器会将这段代码放在紧接着跳转指令的位置，优化 I-Cache
    fast_path();
} else {
    slow_path();
}
```

在 Stable Rust 中，我们可以使用 `#[cold]` 属性标记不常用的函数：

```rust
#[cold]
fn handle_error() {
    // 编译器会把这个函数放到比较远的内存区域，避免污染 I-Cache
}
```

## 3. 乱序执行 (Out-of-Order Execution, OoO)

为了掩盖内存访问的高延迟，现代 CPU（如 Intel Skylake, AMD Zen）都是乱序执行的。

如果指令序列是：
1. `A = load(ptr)` (Cache Miss, 需要 300 周期)
2. `B = A + 1` (依赖 A)
3. `C = 5 * 2` (不依赖 A)

如果是顺序执行，CPU 会在第 1 步卡住 300 个周期，第 3 步也被阻塞。
但在乱序执行中，CPU 会有一个 **重排序缓冲区 (Reorder Buffer, ROB)**。它会发现指令 3 不依赖指令 1 和 2，于是先执行指令 3。

### 3.1 数据依赖链 (Data Dependency Chain)

虽然 OoO 很强大，但它无法打破真正的数据依赖。

```rust
// 强依赖链：必须串行执行
a = b + 1;
c = a + 1;
d = c + 1;
```

```rust
// 无依赖：可以并行执行（利用超标量架构）
a = b + 1;
c = e + 1;
d = f + 1;
```

在 HFT 代码中，我们有时会通过**打破依赖链**来提高指令级并行度 (ILP)。

## 4. 超标量与流水线 (Superscalar & Pipeline)

很多初学者容易混淆“流水线”和“超标量”这两个概念。它们是 CPU 提升性能的两个不同维度：

### 4.1 纵向 vs 横向

*   **流水线 (Pipelining) —— 纵向切分 (Temporal Parallelism)**
    *   **原理**: 将一条指令的执行过程拆分成多个阶段（如 5 级：取指、译码、执行...）。
    *   **效果**: 让 CPU 可以同时处理多条处于**不同阶段**的指令。
    *   **类比**: 工厂的**装配线**。甲在装轮胎，乙在装引擎，丙在喷漆。虽然造一辆车还是要很久，但每分钟都能下线一辆车。
    *   **瓶颈**: 最多只能达到 IPC (Instructions Per Cycle) = 1。即每个周期完成 1 条指令。

*   **超标量 (Superscalar) —— 横向扩展 (Spatial Parallelism)**
    *   **原理**: 在同一个阶段（主要是**执行阶段**）复制多份硬件资源。
    *   **硬件**: 现代 CPU 核心通常有多个执行端口（Port）。例如，它可能有两个整数 ALU，两个浮点 FPU，两个加载/存储单元。
    *   **效果**: CPU 一个周期可以同时发射并执行 4-6 条指令！
    *   **类比**: 工厂开了**多条装配线**。现在有 3 个甲同时装轮胎，3 个乙同时装引擎。
    *   **突破**: 打破了 IPC = 1 的限制，理论上 IPC 可以达到 4 甚至更高。

### 4.2 为什么 SIMD 和循环展开有效？

这就是为什么 SIMD（单指令多数据）和循环展开（Loop Unrolling）如此有效——它们喂饱了 CPU 的所有执行单元。

*   **循环展开**: 
    ```rust
    // 普通循环：每次迭代只有 1 次加法，由于数据依赖，可能只能用 1 个 ALU
    for i in 0..n { acc += data[i]; }

    // 展开循环：打破依赖链，让 CPU 可以同时用 4 个 ALU 计算 acc1, acc2, acc3, acc4
    for i in (0..n).step_by(4) {
        acc1 += data[i];
        acc2 += data[i+1];
        acc3 += data[i+2];
        acc4 += data[i+3];
    }
    ```
    如果不展开，CPU 的其他 ALU 就在“摸鱼”。展开后，超标量架构才能火力全开。

## 5. 计时的真相：TSC (Time Stamp Counter)

在 HFT 中，我们需要测量纳秒级的代码执行时间。标准的 `std::time::Instant::now()` 虽然方便，但它是通过 vDSO 调用 `clock_gettime` 实现的，开销在 20-50ns 左右。对于一段执行时间只有 100ns 的代码，这误差太大了。

### 5.1 RDTSC 指令

x86 CPU 提供了一个寄存器 **TSC (Time Stamp Counter)**，它记录了 CPU 上电以来的时钟周期数。

*   **指令**: `rdtsc` (Read Time-Stamp Counter)。
*   **开销**: 约 20-30 个 **时钟周期** (Cycles)，即 **6-10 纳秒** (ns)。
    *   (假设 CPU 主频 3.0GHz，1 ns ≈ 3 cycles)
*   **精度**: 绝对的 CPU 周期级精度。

```rust
#[cfg(target_arch = "x86_64")]
pub fn rdtsc() -> u64 {
    unsafe {
        use std::arch::x86_64::_rdtsc;
        _rdtsc()
    }
}
```

#### 如何转换为纳秒 (ns)？

TSC 得到的是**周期数**，要转换成时间，必须除以 CPU 的**标称频率 (Base Frequency)**。

1.  **获取频率**: 在 Linux 上，读取 `/proc/cpuinfo` 中的 `tsc_khz`，或者在程序启动时测量一次（Sleep 1秒，看 TSC 增加了多少）。
2.  **转换公式**: `ns = (end_tsc - start_tsc) * 1_000_000_000 / frequency_hz`。
    *   **优化**: 除法太慢（~20-50 cycles）。在 HFT 中，我们将除法转换为乘法：`ns = delta_tsc * mult_factor >> shift`。

#### 如何处理指令开销？

`rdtsc` 本身也有开销（约 20-30 周期）。如果你的代码段非常短（例如只有 50 周期），那么测量误差高达 50%。

**处理方法**:
1.  **空跑校准 (Calibration)**: 测量连续执行两次 `rdtsc` 的差值，作为基准开销。
2.  **减去开销**: `duration = (end - start) - overhead`。

```rust
pub fn measure_overhead() -> u64 {
    let start = rdtsc();
    let end = rdtsc();
    end - start // 这就是测量本身的开销
}
```

### 5.2 陷阱：乱序执行与 RDTSCP

由于 CPU 是乱序执行的，`rdtsc` 可能会被重排到你想要测量的代码块**中间**甚至**后面**执行！

*   **解决方案**: 使用 `rdtscp` 指令。它是一个**序列化 (Serializing)** 指令，保证它前面的所有指令都执行完才读取 TSC。或者在 `rdtsc` 前后加内存屏障 (`lfence` / `mfence`)。

### 5.3 陷阱：变频与 Invariant TSC

早期的 CPU 在降频（节能）时，TSC 也会变慢。这意味着你无法用 TSC 来计算真实时间。
现代 CPU（Nehalem 之后）都有 **Invariant TSC**（恒定 TSC），即使 CPU 降频或休眠，TSC 依然以标称频率（如 3.0GHz）稳定增加。

> **面试题**: "如何在 Rust 中实现一个开销小于 10ns 的计时器？"
> **答案**: "直接封装 `_rdtsc` intrinsic，并在启动时通过 `cpuid` 检查 `invariant_tsc` 标志位，计算出 TSC 频率作为转换因子。"

## 6. 总结

编写低延迟代码不仅仅是写出逻辑正确的代码，更是要写出**对 CPU 友好**的代码：

1.  **减少分支**: 使用数学运算或位运算代替 `if`（Branchless Programming）。
2.  **提高预测率**: 让分支模式尽可能可预测。
3.  **打破依赖**: 让指令之间尽可能独立，利用 CPU 的乱序执行能力。
4.  **利用流水线**: 保持流水线充盈，避免气泡。

下一章，我们将结合具体的内存知识，讲解 [内存布局与缓存效率](memory_layout.md)。
