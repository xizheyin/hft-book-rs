# C++ 编译优化、基准测试与性能工具

C++ 给了开发者很多性能旋钮：`-O3`、LTO、PGO、SIMD、`perf`……但旋钮多不代表应该一起打开。真正可靠的优化流程是：**先定义目标并建立基线，再用工具找到原因，每次只验证一个主要假设。**

本章带你搭起一个最小 CMake 工程，写一个不会轻易被编译器“测没了”的基准程序，再学习 GCC/Clang 优化、LTO、PGO、SIMD、Linux `perf` 和 Sanitizer。你不需要预先熟悉构建系统。

先认识本章会反复出现的最小术语：

| 术语 | 先这样理解 |
|---|---|
| P99 / P99.9 | 分别表示约 99% / 99.9% 的样本不超过该值；样本必须足够多 |
| compiler pass | 编译器流水线中的一次分析或优化步骤 |
| I-cache | CPU 缓存机器指令的区域，代码太分散或膨胀可能增加未命中 |
| build ID | 用来把线上二进制与完全匹配的调试符号对应起来的标识 |
| ISA | Instruction Set Architecture，CPU 能执行的指令体系 |
| SMT | 一个物理核心暴露多个硬件线程，共享部分执行资源 |
| NUMA | 不同 CPU/内存节点之间的访问代价可能不同 |
| multiplex | 硬件计数器不够时，`perf` 分时轮换事件并进行估算 |
| futex | Linux 用于用户态同步原语等待/唤醒的内核机制 |
| IRQ / softirq | 硬件中断及其部分延后处理，可能打断或挤占应用线程 |

## 1. 性能优化是一条证据链

一个可复用的流程是：

1. **定义指标**：优化吞吐，还是 P99/P99.9 延迟？起点和终点在哪里？
2. **固定场景**：记录输入数据、线程数、CPU 绑定、编译器和提交版本。
3. **建立基线**：先确认结果正确，再保存延迟分布和资源指标。
4. **定位原因**：用 profile、硬件计数器和阶段打点形成假设。
5. **做一个主要改动**：避免同时换算法、编译器和线程拓扑。
6. **重新验证**：运行正确性测试、Sanitizer、微基准和端到端回放。
7. **保留或回退**：只有目标指标稳定改善且没有重要回归，才保留改动。

```text
业务症状 -> 可复现基线 -> profile 证据 -> 可证伪假设
        -> 单一改动 -> 正确性回归 -> 性能 A/B -> 上线近似复验
```

“火焰图上这个函数很宽”只是线索；“打开 `-O3` 后本机快了”也只是一次观察。缺少负载和测量边界时，它们都不是可复用结论。

## 2. 编译、链接和 CMake 在做什么

一个 C++ 程序大致经历：

```text
main.cpp
   │  预处理：展开 #include 和宏
   ▼
翻译单元
   │  编译：检查语义并生成汇编/目标代码
   ▼
main.o
   │  链接：把目标文件和库组合起来
   ▼
可执行文件
```

小例子可以直接运行 `g++ main.cpp`，项目一大，命令行很快会塞满源文件、库路径和选项。CMake 的作用是描述“有哪些目标、源文件和依赖”，再为 Ninja、Make 或 IDE 生成真正的构建规则。

### 2.1 一个最小而可扩展的 CMakeLists

假设目录中有本章稍后的 `benchmark.cpp`，旁边新建 `CMakeLists.txt`：

<details>
<summary>动手资料：完整 CMake 配置与构建命令</summary>

```cmake
cmake_minimum_required(VERSION 3.20)
project(cpp_hft_benchmark LANGUAGES CXX)

add_executable(hft_benchmark benchmark.cpp)
target_compile_features(hft_benchmark PRIVATE cxx_std_20)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(hft_benchmark PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wshadow
    )
endif()

option(HFT_KEEP_FRAME_POINTER "Keep frame pointers for profiling" ON)
if(HFT_KEEP_FRAME_POINTER AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(hft_benchmark PRIVATE -fno-omit-frame-pointer)
endif()

option(HFT_ENABLE_NATIVE "Optimize only for the build machine CPU" OFF)
if(HFT_ENABLE_NATIVE AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(hft_benchmark PRIVATE -march=native)
endif()

option(HFT_ENABLE_LTO "Enable interprocedural optimization" OFF)
if(HFT_ENABLE_LTO)
    include(CheckIPOSupported)
    check_ipo_supported(RESULT hft_ipo_supported OUTPUT hft_ipo_error)
    if(NOT hft_ipo_supported)
        message(FATAL_ERROR "LTO is not supported: ${hft_ipo_error}")
    endif()
    set_property(TARGET hft_benchmark
                 PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()
```

构建 Release 版本：

```bash
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release
cmake --build build/release --parallel --verbose
./build/release/hft_benchmark
```

几个关键点：

- `target_compile_features(... cxx_std_20)` 把语言基线设为 C++20；
- 编译选项挂在具体 target 上，不会意外污染所有依赖；
- `--verbose` 可以看到最终传给编译器的真实命令；
- `-Wall -Wextra` 并不是“所有警告”，也不是正确性证明；
- `-Werror` 可在固定工具链的 CI 中使用，但编译器升级会新增警告，应有升级计划；
- 单配置生成器使用 `CMAKE_BUILD_TYPE`；Visual Studio、Xcode 等多配置生成器通常在构建时写 `--config Release`。

不要在 `CMakeLists.txt` 中无条件覆盖用户的 `CMAKE_CXX_FLAGS`。优先使用 target 级配置和 CMake 自带的 IPO 能力，让工具链负责选择相容的编译、链接参数。

</details>

## 3. GCC / Clang 的优化级别

GCC 和 Clang 都接受常见的 `-O` 选项，但具体启用哪些 pass 会随编译器版本、目标架构和上下文变化。不要把某张网络表格当永久契约。

| 选项 | 常见用途 | 注意点 |
| --- | --- | --- |
| `-O0` | 最快编译、逐步调试 | 运行行为和栈形状可能与 Release 差很多 |
| `-Og` | 兼顾一部分优化与调试 | 仍不代表生产构建 |
| `-O2` | 稳健的通用优化起点 | 是否优于 `-O3` 要实测 |
| `-O3` | 更积极的内联、循环与向量化 | 可能增大代码，伤害 I-cache |
| `-Os` / Clang `-Oz` | 更关注代码体积 | 小代码有时反而改善 I-cache |

CMake 的 Release 配置通常会选择优化并定义 `NDEBUG`，但精确选项属于当前平台和工具链配置，应通过 verbose 构建确认。`NDEBUG` 会关闭标准 `assert`；不要把业务风控校验只写在 `assert` 里。

### 3.1 调试信息不等于 Debug 构建

Release 程序可以同时带 `-g`：

```bash
clang++ -std=c++20 -O3 -g -fno-omit-frame-pointer benchmark.cpp -o benchmark
```

`-g` 添加符号信息，通常不会把优化级别改回 `-O0`。它会增大产物或符号文件；部署时可以剥离运行文件，并按 build ID 保存匹配的独立符号。缺少匹配符号时，`perf` 调用栈会充满地址或 `[unknown]`。

`-fno-omit-frame-pointer` 常让栈采样更可靠，但可能占用一个寄存器并改变性能。比较前要让基线与候选版本保持相同配置。

### 3.2 两个需要格外谨慎的开关

**`-march=native`** 允许编译器使用构建机器支持的指令。它适合“构建并运行在同一批固定 CPU”的实验，却可能让二进制在较旧机器上触发 illegal instruction。发布软件应选择明确的最低 ISA，或实现经过测试的运行时分派。

**`-ffast-math`** 允许改变部分 IEEE 浮点语义，例如重排运算，并可能弱化对 NaN、无穷、舍入和有符号零的处理。它不是免费的“更快数学”。金融价格和数量通常优先使用带明确单位的整数；必须使用浮点时，要用边界值和业务不变量验证，不能仅看正常样本。

## 4. 写一个不容易“测错”的基准

下面的完整程序模拟一批订单名义金额计算。它先做小规模正确性检查，再预热，最后记录 40 次批量计算的 P50 和 P99。

```cpp
#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

std::uint64_t calculate_notional(
    std::span<const std::uint64_t> prices_ticks,
    std::span<const std::uint32_t> quantities) {
    if (prices_ticks.size() != quantities.size()) {
        throw std::invalid_argument("prices and quantities must have equal size");
    }

    std::uint64_t total = 0;
    for (std::size_t i = 0; i < prices_ticks.size(); ++i) {
        total += prices_ticks[i] * quantities[i];
    }
    return total;
}

std::size_t nearest_rank_index(std::size_t sample_count,
                               std::size_t percentile) {
    const std::size_t rank =
        (sample_count * percentile + 99) / 100;
    return rank == 0 ? 0 : rank - 1;
}

int main(int argc, char** argv) {
    const std::array<std::uint64_t, 2> test_prices{100, 101};
    const std::array<std::uint32_t, 2> test_quantities{2, 3};
    if (calculate_notional(test_prices, test_quantities) != 503) {
        std::cerr << "correctness check failed\n";
        return 1;
    }

    constexpr std::size_t default_item_count = 1U << 20;
    constexpr std::size_t max_item_count = 10'000'000;
    std::size_t item_count = default_item_count;

    if (argc > 1) {
        try {
            const std::string input{argv[1]};
            std::size_t consumed = 0;
            const auto parsed = std::stoull(input, &consumed);
            if (consumed != input.size() || parsed == 0
                || parsed > max_item_count) {
                std::cerr << "item_count must be an integer in [1, "
                          << max_item_count << "]\n";
                return 1;
            }
            item_count = static_cast<std::size_t>(parsed);
        } catch (const std::exception& error) {
            std::cerr << "invalid item_count: " << error.what() << '\n';
            return 1;
        }
    }

    std::vector<std::uint64_t> prices(item_count);
    std::vector<std::uint32_t> quantities(item_count);
    for (std::size_t i = 0; i < item_count; ++i) {
        prices[i] = 10'000 + (i % 100);
        quantities[i] = 100;
    }

    std::uint64_t checksum = 0;
    for (int warmup = 0; warmup < 5; ++warmup) {
        checksum ^= calculate_notional(prices, quantities);
    }

    constexpr std::size_t repetition_count = 40;
    std::vector<double> samples_us;
    samples_us.reserve(repetition_count);

    for (std::size_t repetition = 0;
         repetition < repetition_count;
         ++repetition) {
        // 每轮改变一个输入，降低编译器把重复计算搬出循环的可能。
        const std::size_t index = repetition % item_count;
        quantities[index] = quantities[index] == 100 ? 101 : 100;

        const auto start = std::chrono::steady_clock::now();
        const auto result = calculate_notional(prices, quantities);
        const auto stop = std::chrono::steady_clock::now();

        checksum ^= result;  // 让计算结果对程序有可观察影响。
        const auto elapsed =
            std::chrono::duration<double, std::micro>(stop - start);
        samples_us.push_back(elapsed.count());
    }

    std::sort(samples_us.begin(), samples_us.end());
    const double p50_us = samples_us[nearest_rank_index(
        samples_us.size(), 50)];
    const double p99_us = samples_us[nearest_rank_index(
        samples_us.size(), 99)];

    std::cout << std::fixed << std::setprecision(3)
              << "items=" << item_count
              << ", p50_batch_us=" << p50_us
              << ", p99_batch_us=" << p99_us
              << ", p50_ns_per_item="
              << (p50_us * 1'000.0 / static_cast<double>(item_count))
              << ", checksum=" << checksum << '\n';
}
```

编译运行：

```bash
g++ -std=c++20 -O3 -g -fno-omit-frame-pointer \
  -Wall -Wextra -Wpedantic benchmark.cpp -o benchmark
./benchmark 1048576
```

这段程序比“调用一次然后看纳秒数”可靠一些，但仍只是教学基准：

- `argc` 是命令行参数数量，`argv` 保存各参数文本；示例拒绝非法文本和过大的教学输入；
- 计时边界只包含求和循环，不包含分配和输入生成；
- 批量计算分摊了时钟调用开销；
- 预热减少首次缺页、冷缓存和动态频率变化的部分影响；
- `checksum` 防止结果完全无用，输入变化降低循环被提升的可能；
- P99 只有 40 个样本，统计置信度很弱，不能当生产尾延迟；
- 无符号溢出在 C++ 中按模运算，但真实名义金额不应静默回绕，应根据业务上界使用 checked 运算或更宽表示。

### 4.1 一份基准记录应包含什么

至少记录：

- CPU 型号、核心/NUMA 拓扑、SMT 状态；
- 操作系统、内核、编译器和链接器版本；
- 完整编译参数与提交 ID；
- 输入规模、数据分布、线程数和队列容量；
- 计时起点、终点、预热和样本数；
- P50/P90/P99/P99.9、吞吐和 CPU 占用；
- 线程亲和性、IRQ 干扰、缺页和温度/频率条件；
- 运行间方差、异常值处理规则和原始样本。

即使教学算例显示“每项平均耗时很小”，也不能把它当成真实系统的单条处理时延：批处理、向量化、缓存命中和计时摊销都会让均值看起来更小。

## 5. LTO：让优化跨越翻译单元

普通编译会分别优化每个 `.cpp`。函数定义位于另一个翻译单元时，编译器可能看不到函数体，无法内联或传播常量。

LTO（Link-Time Optimization，链接时优化）让链接阶段获得更完整的程序信息。CMake 中可使用前面定义的开关：

```bash
cmake -S . -B build/lto \
  -DCMAKE_BUILD_TYPE=Release \
  -DHFT_ENABLE_LTO=ON
cmake --build build/lto --parallel --verbose
```

LTO 可能带来：

- 跨 `.cpp` 内联；
- 删除未使用代码；
- 更完整的常量传播和去虚化。

也可能带来：

- 更长构建和链接时间；
- 更高峰值内存；
- 代码膨胀，反而增加 I-cache 压力；
- 对静态库、链接器插件和工具链一致性的更高要求；
- 栈形状变化，使 profile 对比更难。

GCC、Clang 的 full LTO / ThinLTO 参数和对象格式细节不同。优先让同一套 CMake 工具链管理编译与链接，保存完整命令，并用基准决定是否保留。

## 6. PGO：让真实负载指导优化

PGO（Profile-Guided Optimization，基于剖面的优化）通常分三步：

1. 构建带采集指令的程序；
2. 用**有代表性**的负载训练；
3. 带着 profile 重新编译。

编译器可以利用这些信息调整分支布局、内联和代码布局。关键不是“跑得久”，而是训练流量是否代表生产关键路径。

<details>
<summary>动手资料：GCC 与 Clang 的最小 PGO 命令</summary>

### 6.1 GCC 最小流程

```bash
mkdir -p build/pgo-data
g++ -std=c++20 -O3 -fprofile-generate=build/pgo-data \
  benchmark.cpp -o build/benchmark
./build/benchmark 1048576
g++ -std=c++20 -O3 -fprofile-use=build/pgo-data -fprofile-correction \
  benchmark.cpp -o build/benchmark
```

### 6.2 Clang 最小流程

```bash
mkdir -p build
clang++ -std=c++20 -O3 -fprofile-instr-generate \
  benchmark.cpp -o build/benchmark
LLVM_PROFILE_FILE="build/benchmark-%p.profraw" \
  ./build/benchmark 1048576
llvm-profdata merge -output=build/benchmark.profdata build/*.profraw
clang++ -std=c++20 -O3 \
  -fprofile-instr-use=build/benchmark.profdata \
  benchmark.cpp -o build/benchmark
```

这些命令用于理解流程；真实项目应让 CMake/CI 管理相同的编译参数和 profile 产物。训练后要检查 missing/stale profile 警告，不能悄悄退回无 PGO 构建。

</details>

PGO 的常见故障模式：

- 只用“平静行情”训练，极端路径反而布局更差；
- 训练的二进制与使用 profile 的源码不匹配；
- 只比较训练数据，形成过拟合；
- profile 文件被不同构建并发覆盖；
- P50 改善但 P99.9、代码体积或启动时间恶化。

应把流量按平静、开盘、突发和异常/拒单路径分层，保留独立验证集，并在目标硬件上做端到端 A/B。

## 7. SIMD：一次处理多个元素

SIMD（Single Instruction, Multiple Data）让一条指令并行处理多个整数或浮点数。上一节基准中的连续数组求和，就是编译器可能自动向量化的形状。

### 7.1 先看编译器报告

知道“先让编译器报告是否向量化、再看汇编和端到端指标”即可。不同编译器的精确参数属于查阅型知识：

<details>
<summary>动手资料：GCC / Clang 向量化报告命令</summary>

GCC：

```bash
g++ -std=c++20 -O3 -march=native \
  -fopt-info-vec-optimized -fopt-info-vec-missed \
  benchmark.cpp -o benchmark
```

Clang：

```bash
clang++ -std=c++20 -O3 -march=native \
  -Rpass=loop-vectorize -Rpass-missed=loop-vectorize \
  benchmark.cpp -o benchmark
```

报告只能告诉你编译器做了什么或为什么放弃，不能证明向量化后端到端更快。还要检查汇编和目标指标。

</details>

### 7.2 更容易自动向量化的数据形状

- 连续数组，访问步长固定；
- 把 `price[]`、`quantity[]` 分开保存的 SoA（Structure of Arrays）；
- 循环体分支少；
- 编译器能证明指针不别名；
- 工作批次足够大，能摊薄边界处理。

但 HFT 不是所有路径都适合 SIMD：单条消息解析、分支复杂状态机和链式指针访问可能没有足够并行元素。为了凑批次而等待更多消息，还可能提高单条消息延迟。

### 7.3 手写 intrinsic 前先回答四个问题

1. 最低支持哪种 ISA：SSE、AVX2，还是 AVX-512？
2. 非对齐输入和不足一个向量宽度的尾部如何处理？
3. 部署到不支持该指令的 CPU 时如何运行时分派？
4. 更宽向量是否引起频率变化，并实际改善 P99/P99.9？

手写 intrinsic 是平台相关代码，应封装在小模块里，保留标量参考实现做逐项差分测试。不要只验证“正常长度正好是 8 的倍数”的输入。

## 8. 用 perf 回答“CPU 时间花在哪里”

`perf` 是 Linux 的性能分析工具集合。它既能统计硬件事件，也能采样调用栈。权限由系统的 `perf_event_paranoid`、容器设置和内核配置决定；命令失败时先确认环境，不要直接使用高权限绕过生产安全策略。

### 8.1 `perf stat`：先看总体现象

```bash
perf stat -r 10 \
  -e task-clock,cycles,instructions,branches,branch-misses,cache-misses \
  ./benchmark 1048576
```

可以辅助观察：

- cycles 与 instructions：工作量和每周期指令数的线索；
- branch-misses：分支预测失败线索；
- cache-misses：某类缓存 miss 线索；
- task-clock 与 elapsed time：CPU 时间和墙上时间的关系。

不要跨 CPU 型号直接比较原始事件数。事件的精确定义依处理器而异；同时采集太多事件时可能 multiplex，要查看事件实际运行比例。可以计算 MPKI（每千条指令的 miss）等归一化指标，但它仍只是定位线索。

### 8.2 `perf record/report`：找到 On-CPU 热点

```bash
perf record -F 199 -g -- ./benchmark 1048576
perf report
```

- `-F 199` 表示每秒约 199 次采样；频率越高，开销和数据量通常越大；
- `-g` 采集调用栈；符号、frame pointer 或 unwind 信息不完整时，栈会断；
- 热点宽度近似表示被采到的 On-CPU 时间，不是调用发生的时间顺序。

最宽函数不一定值得优化：它可能是必要计算、非关键线程，或刻意 busy-poll。必须把 profile 与业务阶段和慢样本关联。

### 8.3 CPU 不高但 P99 很差怎么办

普通 CPU profile 只看线程正在 CPU 上运行的时间。线程可能在等待：

- run queue 调度；
- futex / mutex；
- I/O、缺页或内存回收；
- 另一个队列 owner；
- IRQ / softirq 干扰。

这时要看 context switch、run-queue delay 和 off-CPU 时间，可结合 `perf sched`、tracepoint 或经过评估的 eBPF 工具。先用端到端 trace 找到慢事件所在时间窗；全程平均火焰图很容易把稀有 P99.9 尖峰淹没。

## 9. 基准测试的常见陷阱

### 9.1 编译器把工作删掉了

如果结果从不被使用，优化器可以删除整个计算。应让结果产生可观察影响，并检查生成汇编。不要把每轮 `std::cout` 放进计时区，因为 I/O 会盖住被测函数。

### 9.2 计时器比工作还贵

测一个只有几条指令的函数时，时钟调用成本可能占主导。可以批量执行很多次，再除以操作数；同时报告批次大小，不能只展示除完后的漂亮数字。

### 9.3 Debug 和 Release 混比

Debug 版本常关闭内联和多种优化；它适合调试，不适合代表生产性能。基线与候选应使用相同的优化、符号、LTO/PGO、分配器和链接方式。

### 9.4 只看平均数

平均值会隐藏罕见长尾。报告分位数、最大值、吞吐、CPU 占用和运行间方差；P99.9 需要足够样本，否则只是给一个样本贴上精确标签。

### 9.5 为“稳定”而改坏真实环境

绑核、CPU 频率、SMT、NUMA 和 IRQ 都会影响结果，但不要未经评估就在共享或生产机器上修改系统设置。记录现状，在隔离测试环境中逐项实验，并说明结果适用的拓扑。

### 9.6 微基准赢，端到端输

更激进的内联可能让小函数快一点，却因代码膨胀伤害真实系统的 I-cache；批处理提高吞吐，却增加单条等待时间。微基准用于隔离机制，最终决策要回到代表性行情回放和端到端延迟。

## 10. Sanitizer：性能之前先排除未定义行为

优化构建会利用“合法程序没有 UB”的假设。越激进的优化，越可能让潜伏错误表现得离奇。因此性能改动应先过测试和动态检查。

### 10.1 ASan + UBSan

```bash
clang++ -std=c++20 -O1 -g -fno-omit-frame-pointer -pthread \
  -fsanitize=address,undefined spsc_queue.cpp -o spsc_asan
./spsc_asan
```

- ASan（AddressSanitizer）擅长发现越界、use-after-free 等内存错误；
- UBSan（UndefinedBehaviorSanitizer）能发现一部分未定义行为，例如某些有符号溢出和错误移位；
- 它们不能覆盖所有输入和所有 UB，没报错不等于程序已证明安全。

### 10.2 TSan

```bash
clang++ -std=c++20 -O1 -g -fno-omit-frame-pointer -pthread \
  -fsanitize=thread spsc_queue.cpp -o spsc_tsan
./spsc_tsan
```

TSan（ThreadSanitizer）用于发现许多数据竞争。它理解标准原子同步，但不能证明无锁算法的业务不变量，也未必发现“Ordering 过弱但本次交错没触发”的问题。

通常不要把 ASan 和 TSan 放在同一个二进制中；分别构建、分别运行。Sanitizer 会显著改变内存布局、调度和速度，**不能拿 Sanitizer 下的延迟当生产性能数据**。GCC 也支持这些常见选项，但平台支持、运行库和报告细节需由当前工具链验证。

### 10.3 建议的构建矩阵

| 构建 | 目的 | 是否用于性能结论 |
| --- | --- | --- |
| Debug + 单元测试 | 快速定位逻辑问题 | 否 |
| ASan + UBSan | 内存与部分 UB | 否 |
| TSan | 数据竞争 | 否 |
| Release + symbols | profile 和基准 | 是 |
| Release + LTO/PGO 候选 | 优化 A/B | 是，需与基线同场比较 |

Sanitizer、静态分析和代码评审互相补充；没有任何一个工具可以单独证明 C++ 并发代码正确。

## 11. C++ 与 Rust 工具对照

| 任务 | C++ 常用方式 | Rust 常用方式 |
| --- | --- | --- |
| 项目构建 | CMake + Ninja/Make，GCC/Clang | Cargo + rustc |
| Release 优化 | `-O2` / `-O3` | Cargo `[profile.release]` |
| LTO | CMake IPO、编译器 LTO/ThinLTO | Cargo profile 中配置 LTO |
| PGO | GCC gcov profile、LLVM profile | rustc/LLVM PGO 流程 |
| 微基准 | Google Benchmark、自建 harness | Criterion、自建 harness |
| CPU profiling | `perf`、平台 profiler | 同样可用 `perf`、平台 profiler |
| 动态错误检查 | ASan / UBSan / TSan | Miri、Sanitizer（依工具链）、Loom 等 |

`perf` 观察的是进程和硬件，不关心源码来自 C++ 还是 Rust。两种语言都需要匹配的符号、明确的测量边界和代表性负载。工具名称不同，实验方法相同。

## 12. HFT 场景：优化一条行情到信号路径

假设端到端 P99 相比稳定基线明显上升，可以按下面顺序处理：

1. 明确定时边界：网卡时间戳、用户态收包、解码、订单簿更新、信号完成分别在哪里；
2. 保存慢事件的 trace ID、CPU、队列深度和阶段耗时；
3. 检查是否排队、丢包恢复、缺页、调度或 IRQ，而不是直接盯 CPU 热点；
4. 对对应时间窗采集 On-CPU / off-CPU 与硬件事件；
5. 形成一个假设，例如“订单簿 AoS 布局导致热点字段跨太多缓存行”；
6. 做最小改动，保留功能差分测试；
7. 在相同回放上比较正确性、P50/P99/P99.9、吞吐和 CPU；
8. 若微基准改善但端到端无改善，就不把它包装成业务胜利。

只有证据指向编译器可见性、分支布局或数据并行时，才分别尝试 LTO、PGO 或 SIMD。把三者同时打开，会让你不知道收益和回归来自哪里。

## 13. 面试追问与参考答法

### Q1：`-O3` 一定比 `-O2` 快吗？

不一定。更积极的内联和向量化可能提升热点，也可能导致代码膨胀、I-cache 压力和编译时间上升。要在相同工具链、目标硬件和负载下比较端到端分布。

### Q2：火焰图最宽的函数就是第一优化目标吗？

不一定。宽度表示 On-CPU 采样占比，它可能是必要工作、busy-poll 或不在目标关键路径。应关联业务进度点和慢 trace，再做可证伪实验。

### Q3：为什么保留 `-g` 不等于 Debug？

`-g` 主要添加调试信息；优化级别由 `-O` 决定。带符号的 Release 有利于 profile，但要记录符号、frame pointer 和构建 ID，并验证产物布局影响。

### Q4：PGO 为什么会让结果变差？

训练流量可能不代表生产，profile 可能过期，热点布局可能牺牲冷但重要的异常路径，代码体积也可能变化。应使用分层训练与独立验证流量。

### Q5：TSan 通过是否证明 SPSC Ordering 正确？

不能。TSan 能发现许多实际执行到的数据竞争，但不枚举所有交错，也不证明满空、槽位所有权、回绕和对象生命周期不变量。需要人工证明、针对性测试和目标架构压力测试。

## 14. 易错点

1. **没有正确性基线就测性能**：一个算错结果的程序往往“特别快”。
2. **把编译器选项一次全开**：无法判断哪个选项带来收益或回归。
3. **用 `-march=native` 构建通用发布包**：旧 CPU 可能无法运行。
4. **把 `-ffast-math` 当安全默认值**：可能改变业务依赖的浮点语义。
5. **只报告平均值和最好一次**：隐藏尾延迟与运行间波动。
6. **让编译器删除被测代码**：结果未使用，或输入在编译期完全可知。
7. **把 Sanitizer 速度当生产速度**：插桩显著改变布局和调度。
8. **只看 On-CPU profile**：排队、锁、调度和 I/O 等 off-CPU 问题会被漏掉。
9. **PGO 用训练集自证**：应保留独立验证回放，检查异常路径。
10. **看到 SIMD 报告就宣布提速**：仍需处理尾部、ISA 兼容和端到端批处理延迟。

## 做题方法

性能诊断题建立“现象 → 假设 → 指标 → 实验 → 结论”的证据链：

1. 明确要优化的指标与工作负载，区分端到端时间、CPU time、吞吐和尾部延迟；先保存可重复基线。
2. 用 profiler 找时间或样本集中位置，而不是从最显眼的源码开始；检查采样频率、符号和测量本身的扰动。
3. 对热点提出可证伪假设，例如分支失误、Cache miss、锁等待或分配；为每个假设选择能直接支持或反驳的计数器/trace。
4. 一次只改变一个主要因素，保持编译器、频率、亲和性、输入和预热一致；报告分布与重复次数，不只报最好一次。
5. 查看优化后汇编或 IR，确认源码修改确实改变预期机制；若指标改善但端到端无变化，继续按 Amdahl 定律找剩余部分。
6. 运行正确性、sanitizer 和回归测试，防止通过删工作、改变结果或引入 UB 获得虚假加速。

验算要求结论同时回答“哪个机制变了”和“它对目标指标贡献多少”。只有 benchmark 变快而缺少机制证据，仍可能是噪声或工作量变化。

## 15. 练习与参考答案

### 练习 1

基准显示候选版本的平均值改善，但 P99.9 明显变差，关键路径应该直接上线吗？

<details>
<summary>参考答案</summary>

不能直接上线。先确认样本量、噪声和计时边界，再定位 P99.9 变差原因。若业务目标包含尾延迟，平均值改善不能抵消重要长尾回归。还需通过正确性测试和代表性端到端回放。

</details>

### 练习 2

`perf report` 显示 35% 样本在轮询队列的函数中，这是否证明队列实现太慢？

<details>
<summary>参考答案</summary>

不证明。线程可能被设计为 busy-poll，空闲时自然把大量 On-CPU 样本留在轮询函数。应查看队列占用、消息年龄、有效工作吞吐，以及慢事件是否真的卡在这里。

</details>

### 练习 3

为什么 PGO 训练应包含开盘突发和拒单路径，而不只包含正常行情？

<details>
<summary>参考答案</summary>

PGO 会根据训练频率调整分支、内联和代码布局。只训练平静行情可能让极端但关键的路径布局变差，而那些路径恰恰决定过载时的尾延迟与风控行为。

</details>

### 练习 4

ASan、UBSan、TSan 都通过后，还需要做什么？

<details>
<summary>参考答案</summary>

仍需代码评审、单元/集成/压力测试，并发不变量与 happens-before 证明，以及 Release 构建下的目标架构验证。这些工具只覆盖实际执行到且各自能够检测的一部分错误。

</details>

### 练习 5

准备比较 `-O2` 和 `-O3`，哪些条件至少要保持一致？

<details>
<summary>参考答案</summary>

保持源码提交、编译器/链接器、其他 flags、依赖、输入数据、线程数、CPU/NUMA 绑定、预热、计时边界和系统环境一致。分别保存多次原始样本，并同时检查正确性、代码体积、P50/P99/P99.9、吞吐和 CPU。

</details>

## 16. 小结

- 优化从业务目标和可复现基线开始，不从编译器开关开始；
- CMake 应以 target 为单位表达 C++20、警告、LTO 和平台选项；
- `-O3`、LTO、PGO、SIMD 都有适用条件，也都可能造成回归；
- 微基准必须防止工作被优化掉，清楚记录批次、预热、样本和计时边界；
- `perf stat` 看总体事件，`perf record` 看 On-CPU 热点，长尾还要检查 off-CPU；
- ASan、UBSan、TSan 用于发现不同类别的错误，插桩结果不能代表生产性能；
- HFT 最终应在目标硬件和代表性回放上比较正确性、吞吐与完整延迟分布。

进一步阅读：[GCC Optimize Options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)、[Clang Users Manual](https://clang.llvm.org/docs/UsersManual.html)、[CMake IPO 支持](https://cmake.org/cmake/help/latest/module/CheckIPOSupported.html) 与 [`perf` Wiki](https://perf.wiki.kernel.org/)。
